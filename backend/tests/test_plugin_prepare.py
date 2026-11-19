"""Synthetic resumed import exercises the real Lua completion request and API contract."""
from pathlib import Path

from fastapi.testclient import TestClient
from lupa.lua51 import LuaRuntime

from lrc_selection.app import create_app

PLUGIN = Path(__file__).resolve().parents[2] / 'plugin/lrc-photo-selection.lrplugin'


def test_resumed_new_import_sends_json_null_and_preserves_uploaded_previews(tmp_path):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(r'''
        test = {}
        local photo = {localIdentifier=1}
        function photo:requestJpegThumbnail() error('Ready preview must not be regenerated') end
        local catalog = {}
        function catalog:getTargetPhoto() return photo end
        function catalog:getTargetPhotos() return {photo} end
        function catalog:batchGetRawMetadata()
            return {[photo]={uuid='synthetic-photo',rating=0,lastEditTime=100}}
        end
        function catalog:batchGetFormattedMetadata()
            return {[photo]={fileName='SYNTHETIC.jpg'}}
        end
        local manifest = {schema_version=1,id='synthetic-import',title='SYNTHETIC',catalog_id='synthetic-cat',
            photos={{id='synthetic-photo:1',uuid='synthetic-photo',local_id=1,filename='SYNTHETIC.jpg',
                baseline_rating=0,baseline_edit_time=100,is_virtual_copy=false}}}
        local common = {
            run=function(_, fn) fn({}) end,
            token=function() end,
            catalog=function() return catalog, '/synthetic/catalog.lrcat', 'SYNTHETIC' end,
            registration=function() return 'synthetic-cat' end,
            file=function() return 'synthetic-pending' end,
            read=function() return {manifest=manifest} end,
            assertCatalog=function() end,
            key=function(value) return value end,
            write=function(_, value) assert(value.completed); test.completed=true end,
            openBrowser=function() test.opened=true end,
            request=function(method, path, data)
                if path == '/api/imports' then
                    assert(method == 'POST')
                    test.manifest=data
                    return {status='importing',photos={{id='synthetic-photo:1',preview_ready=true}}}
                end
                assert(method=='POST' and path=='/api/services/synthetic-import/complete')
                assert(type(data)=='string')
                test.payload=data
                return {}
            end,
        }
        package.loaded.Common=common
        package.loaded.Selection={}
        package.loaded.Guide={button=function() return {} end}
        local sdk = {
            LrDialogs={confirm=function() return 'ok' end},
            LrProgressScope=function()
                return {isCanceled=function() return false end,setPortionComplete=function() end,done=function() end}
            end,
        }
        function import(name) return sdk[name] or {} end
    ''')
    lua.execute((PLUGIN / 'Prepare.lua').read_text())
    result = lua.globals().test
    assert result.completed and result.opened
    assert result.payload == 'null'
    codec = lua.execute((PLUGIN / 'JSON.lua').read_text())
    app = create_app(tmp_path, token='synthetic-local-token')
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer synthetic-local-token'
        headers = {'Content-Type': 'application/json'}
        assert client.post('/api/imports', content=codec.encode(result.manifest), headers=headers).status_code == 200
        endpoint = '/api/services/synthetic-import/complete'
        assert client.post(endpoint, content='{}', headers=headers).status_code == 422
        response = client.post(endpoint, content=result.payload, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'ready'
