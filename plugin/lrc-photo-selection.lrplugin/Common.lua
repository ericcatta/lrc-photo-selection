local M = {}
local Application = import 'LrApplication'
local Context = import 'LrFunctionContext'
local Date = import 'LrDate'
local Dialogs = import 'LrDialogs'
local File = import 'LrFileUtils'
local Http = import 'LrHttp'
local MD5 = import 'LrMD5'
local Passwords = import 'LrPasswords'
local Path = import 'LrPathUtils'
local Tasks = import 'LrTasks'
local JSON = require 'JSON'
local root = Path.child(Path.getStandardFilePath('appData'), 'lrc-photo-selection-plugin')
local url = 'http://127.0.0.1:8765'
local tokenKey = 'loopback-token'
local running = false
local storagePaths = {}

function M.run(name, action)
    Context.postAsyncTaskWithContext(name, function(context)
        if running then
            Dialogs.message('Selezione fotografie', 'Un comando del plugin è già in corso.', 'warning')
            return
        end
        running = true
        context:addCleanupHandler(function() running = false end)
        local ok, why = Tasks.pcall(action, context)
        if not ok then Dialogs.message('Selezione fotografie', tostring(why), 'critical') end
    end)
end

function M.catalog()
    local catalog = assert(Application.activeCatalog(), 'Nessun catalogo attivo.')
    local path = assert(catalog:getPath(), 'Percorso del catalogo non disponibile.')
    return catalog, path, Path.leafName(path)
end

function M.assertCatalog(path)
    local _, active = M.catalog()
    assert(active == path, 'Il catalogo attivo è cambiato. Operazione interrotta.')
end

function M.key(value)
    assert(type(value) == 'string' and #value <= 200 and value:match('^[%w_:-]+$'), 'Identificativo non valido.')
    return value
end

function M.file(kind, key)
    local dir = Path.child(root, M.key(kind))
    assert(File.createAllDirectories(dir), 'Impossibile creare lo spazio dati del plugin.')
    local path = Path.child(dir, M.key(key):gsub(':', '_') .. '.json')
    storagePaths[path] = true
    return path
end

local function assertStoragePath(path)
    assert(storagePaths[path], 'Percorso esterno allo spazio dati del plugin.')
end

local function existsFile(path)
    local kind = File.exists(path)
    assert(not kind or kind == 'file', 'File di stato non valido.')
    return kind
end

function M.read(path)
    assertStoragePath(path)
    -- A crash between the two moves leaves the previous committed value intact.
    local source = existsFile(path) and path or
        (existsFile(path .. '.previous') and path .. '.previous')
    if not source then
        assert(not existsFile(path .. '.pending') and not existsFile(path .. '.tmp'), 'Stato locale incompleto. Operazione interrotta.')
        return nil
    end
    local value = JSON.decode(assert(File.readFile(source), 'Impossibile leggere lo stato del plugin.'))
    assert(type(value) == 'table', 'Contenuto dello stato locale non valido.')
    return value
end

function M.write(path, value)
    assertStoragePath(path)
    local serialized = JSON.encode(value)
    local pending, previous = path .. '.pending', path .. '.previous'
    local function remove(file)
        if existsFile(file) then
            assert(File.delete(file), 'Impossibile aggiornare lo stato locale.')
        end
    end
    -- Never remove the last committed copy, including after an interrupted move.
    if not existsFile(path) and existsFile(previous) then
        assert(File.move(previous, path), 'Impossibile recuperare lo stato locale.')
    end
    -- An orphan first-write pending file requires investigation, not replacement.
    assert(existsFile(path) or (not existsFile(pending) and not existsFile(path .. '.tmp')), 'Stato locale incompleto. Operazione interrotta.')
    remove(pending)
    local handle = assert(io.open(pending, 'wb'), 'Impossibile aprire il file di stato del plugin.')
    local wrote = handle:write(serialized)
    local flushed = handle:flush()
    local closed = handle:close()
    assert(wrote and flushed and closed, 'Impossibile registrare lo stato locale. Operazione interrotta.')
    if existsFile(path) then
        remove(previous)
        assert(File.move(path, previous), 'Impossibile conservare lo stato locale precedente.')
    end
    assert(File.move(pending, path), 'Impossibile registrare lo stato locale. Operazione interrotta.')
end

local function digest(value)
    local hex = MD5.digest(value)
    if #hex == 16 then hex = hex:gsub('.', function(char) return string.format('%02x', char:byte()) end) end
    assert(#hex == 32 and hex:match('^%x+$'), 'Digest del catalogo non valido.')
    return hex:lower()
end

function M.newID(seed)
    local hex = digest(seed .. ':' .. string.format('%.17g', Date.currentTime()) .. ':' .. tostring({}))
    return hex:sub(1,8) .. '-' .. hex:sub(9,12) .. '-4' .. hex:sub(14,16)
        .. '-8' .. hex:sub(18,20) .. '-' .. hex:sub(21,32)
end

function M.registration(path, create)
    local file = M.file('catalogs', digest(path))
    local record = M.read(file)
    if not record and create then
        record = { id = M.newID(path), path = path }
        M.write(file, record)
    end
    assert(record and record.path == path, 'Questo catalogo non è registrato nella web app.')
    return M.key(record.id)
end

function M.token(newToken)
    local token = newToken or Passwords.retrieve(tokenKey)
    assert(type(token) == 'string' and #token >= 20 and token:match('^[%w_-]+$'),
        'Configura un token valido dal comando Configura connessione locale.')
    return token
end

function M.saveToken(token)
    Passwords.store(tokenKey, M.token(token))
end

function M.openBrowser(token)
    Http.openUrlInBrowser(url .. '/#token=' .. M.token(token))
end

function M.request(method, endpoint, data, contentType, token)
    local headers = {{ field = 'Authorization', value = 'Bearer ' .. M.token(token) }}
    local response, meta
    if method == 'GET' then
        response, meta = Http.get(url .. endpoint, headers, 15)
    else
        headers[2] = { field = 'Content-Type', value = contentType or 'application/json' }
        local payload = type(data) == 'string' and data or JSON.encode(data)
        response, meta = Http.post(url .. endpoint, payload, headers, method, 30)
    end
    local status = meta and meta.status
    assert(type(status) == 'number', 'Backend locale non raggiungibile. Verifica che sia avviato.')
    if status < 200 or status >= 300 then
        local ok, body = pcall(JSON.decode, response or '')
        local reason = ok and type(body) == 'table' and body.detail
        error('Backend locale (' .. status .. '): ' .. (type(reason) == 'string' and reason or 'richiesta rifiutata.'), 0)
    end
    return JSON.decode(response)
end
return M
