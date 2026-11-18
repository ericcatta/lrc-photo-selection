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
    return Path.child(dir, M.key(key):gsub(':', '_') .. '.json')
end

function M.read(path)
    local exists = File.exists(path)
    if not exists then return nil end
    assert(exists == 'file', 'File di stato non valido.')
    return JSON.decode(assert(File.readFile(path), 'Impossibile leggere lo stato del plugin.'))
end

function M.write(path, value)
    local serialized = JSON.encode(value)
    local temporary = path .. '.tmp'
    local handle = assert(io.open(temporary, 'wb'), 'Impossibile aprire il file di stato del plugin.')
    local wrote = handle:write(serialized)
    local flushed = handle:flush()
    local closed = handle:close()
    assert(wrote and flushed and closed and os.rename(temporary, path), 'Impossibile registrare lo stato locale. Operazione interrotta.')
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
