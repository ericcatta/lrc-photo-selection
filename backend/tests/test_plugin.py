"""Lua SDK simulation: no Lightroom process or catalog is accessed."""
from pathlib import Path
import pytest
from lupa.lua51 import LuaRuntime

PLUGIN = Path(__file__).resolve().parents[2] / 'plugin/lrc-photo-selection.lrplugin'


def test_lua51_syntax_and_json_timestamp_precision():
    runtime = LuaRuntime(unpack_returned_tuples=True)
    compile_lua = runtime.eval('function(s) return assert(loadstring(s)) end')
    for path in PLUGIN.glob('*.lua'):
        compile_lua(path.read_text())
    codec = runtime.execute((PLUGIN / 'JSON.lua').read_text())
    value = 798123456.1234567
    assert codec.decode(codec.encode(value)) == value
    assert codec.decode(codec.encode('Matrimonio — à')) == 'Matrimonio — à'


def simulate(current=0, edited=100, xmp=True, target=1, previous=False, fail_journal=False, cancel=False, claim=True):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().options = lua.table_from({'current': current, 'edited': edited, 'xmp': xmp, 'target': target,
                                          'previous': previous, 'failJournal': fail_journal, 'cancel': cancel, 'claim': claim})
    lua.execute(r'''
      test = { writes=0, claimed=false, files={}, events={} }
      local props
      local photo = {localIdentifier=1}
      function photo:getRawMetadata(key)
        if key == 'uuid' then return 'photo-uuid' end
        if key == 'rating' then return options.current end
        if key == 'lastEditTime' then return options.edited end
        error('Unexpected metadata read: ' .. key)
      end
      function photo:setRawMetadata(key, value)
        assert(key == 'rating' and value == 1, 'Only one-star mutation allowed')
        assert(test.files['rating-cat/photo-uuid:1'], 'Journal must precede write')
        assert(test.claimed, 'Backend claim must precede write')
        test.writes = test.writes + 1
        options.current = value
        table.insert(test.events, 'rating')
      end
      local catalog = {}
      function catalog:findPhotoByUuid(uuid) return photo end
      function catalog:getAllPhotos() return {photo} end
      function catalog:withWriteAccessDo(name, fn, params) fn(); return 'executed' end
      local item = {photo_id='photo-uuid:1', uuid='photo-uuid', local_id=1,
                    expected_rating=0, expected_edit_time=100, target_rating=options.target}
      local service = {id='service', title='SYNTHETIC', catalog_id='cat', revision=1, status='ready',
        photos={{id='photo-uuid:1',uuid='photo-uuid',local_id=1,baseline_rating=0,baseline_edit_time=100}}}
      local plan = {schema_version=1, batch_id='batch',service_id='service',catalog_id='cat',revision=1,items={item}}
      if options.previous then test.files['rating-cat/photo-uuid:1'] = {batch_id='old-batch'} end
      local common = {}
      function common.run(_, fn) local ok, err=pcall(fn, {}); if not ok then test.error=tostring(err) end end
      function common.catalog() return catalog, '/synthetic/catalog.lrcat', 'Synthetic catalog' end
      function common.registration() return 'cat' end
      function common.key(value) return value end
      function common.assertCatalog() end
      function common.file(kind,key) return kind .. '/' .. key end
      function common.read(path) return test.files[path] end
      function common.write(path,value)
        if options.failJournal and path:match('^rating') then error('Synthetic disk failure') end
        test.files[path]=value
        table.insert(test.events, 'journal')
      end
      function common.request(method,path,data)
        if path == '/api/services' then return {service} end
        if path == '/api/services/service' then return service end
        if path:match('/rating%-plan/latest$') then return plan end
        if path:match('/rating%-plan/claim$') then
          if not options.claim then error('Synthetic stale plan') end
          test.claimed=true; return {ok=true}
        end
        if path:match('/rating%-receipts$') then test.receipt=data; return {ok=true} end
        error('Unexpected request ' .. path)
      end
      package.loaded.Common = common
      local view = {}
      for _, name in ipairs({'column','static_text','popup_menu','checkbox'}) do view[name]=function(_,v) return v end end
      local sdk = {
        LrBinding={makePropertyTable=function() props={}; return props end},
        LrView={osFactory=function() return view end, bind=function(value) return value end},
        LrDialogs={
          presentModalDialog=function(dialog)
            if dialog.title == 'Conferma applicazione stelle' then props.xmpChecked=options.xmp end
            return 'ok'
          end,
          message=function() end,
        },
        LrProgressScope=function()
          return {isCanceled=function() return options.cancel end, setPortionComplete=function() end, done=function() end}
        end,
      }
      function import(name) return assert(sdk[name], name) end
    ''')
    lua.execute((PLUGIN / 'Apply.lua').read_text())
    return lua.globals().test


def test_only_zero_to_one_after_claim_and_journal():
    result = simulate()
    assert result.error is None
    assert result.writes == 1
    assert result.receipt.results[1].status == 'applied'
    assert result.receipt.results[1].before == 0
    assert result.receipt.results[1].after == 1


@pytest.mark.parametrize('rating', [1, 3, 5])
def test_existing_stars_are_not_overwritten(rating):
    result = simulate(current=rating)
    assert result.writes == 0
    assert result.receipt.results[1].status == 'conflict'


def test_manual_edit_after_import_is_preserved():
    result = simulate(edited=101)
    assert result.writes == 0
    assert result.receipt.results[1].status == 'conflict'


@pytest.mark.parametrize('options', [{'xmp': False}, {'target': 5}, {'claim': False}, {'fail_journal': True}])
def test_unsafe_or_unverified_conditions_never_write(options):
    result = simulate(**options)
    assert result.writes == 0
    assert result.error is not None


def test_previous_attempt_and_user_cancellation_never_write():
    for options in [{'previous': True}, {'cancel': True}]:
        result = simulate(**options)
        assert result.writes == 0
        assert result.receipt.results[1].status == 'skipped'
