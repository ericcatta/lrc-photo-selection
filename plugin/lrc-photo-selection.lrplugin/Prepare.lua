local Common = require 'Common'
local Binding = import 'LrBinding'
local Date = import 'LrDate'
local Dialogs = import 'LrDialogs'
local Progress = import 'LrProgressScope'
local Tasks = import 'LrTasks'
local View = import 'LrView'

local function metadata(catalog, photos)
    local raw = catalog:batchGetRawMetadata(photos,
        { 'uuid', 'rating', 'lastEditTime', 'dateTimeOriginal', 'isVirtualCopy', 'isVideo' })
    local formatted = catalog:batchGetFormattedMetadata(photos, { 'fileName', 'cameraModel', 'cameraSerialNumber' })
    local manifest, objects = {}, {}
    for _, photo in ipairs(photos) do
        local values = raw[photo]
        if not values.isVideo then
            local uuid, localID = Common.key(values.uuid), photo.localIdentifier
            assert(type(localID) == 'number' and localID >= 0 and localID % 1 == 0, 'Identificativo Lightroom non valido.')
            local id = uuid .. ':' .. string.format('%.0f', localID)
            assert(not objects[id], 'Identificativi Lightroom duplicati.')
            local shown = formatted[photo]
            local camera = shown.cameraModel or 'Sconosciuta'
            if shown.cameraSerialNumber and shown.cameraSerialNumber ~= '' then camera = camera .. ' · ' .. shown.cameraSerialNumber end
            local taken = values.dateTimeOriginal
            manifest[#manifest + 1] = {
                id = id, uuid = uuid, local_id = localID, filename = shown.fileName or id,
                camera = camera, captured_at = type(taken) == 'number' and Date.timeToPosixDate(taken) or nil,
                baseline_rating = values.rating or 0, baseline_edit_time = values.lastEditTime,
                is_virtual_copy = values.isVirtualCopy == true,
            }
            objects[id] = photo
        end
    end
    return manifest, objects
end

local function askTitle(context, label, count)
    local properties = Binding.makePropertyTable(context)
    properties.title = ''
    local view = View.osFactory()
    local answer = Dialogs.presentModalDialog {
        title = 'Prepara servizio',
        contents = view:column {
            bind_to_object = properties,
            view:static_text { title = 'Catalogo: ' .. label },
            view:static_text { title = tostring(count) .. ' fotografie nella selezione attuale.' },
            view:edit_field { value = View.bind 'title', width_in_chars = 42 },
        }, actionVerb = 'Prepara anteprime', cancelVerb = 'Annulla',
    }
    if answer ~= 'ok' then return nil end
    local title = properties.title:match('^%s*(.-)%s*$')
    assert(#title > 0 and #title <= 200, 'Inserisci un titolo di servizio valido.')
    return title
end

local function preview(photo, progress)
    local finished, data, request = false, nil, nil
    request = photo:requestJpegThumbnail(1200, 1200, function(jpeg)
        data, finished = jpeg, true
        request = nil
    end)
    if finished then request = nil end
    local attempts = 0
    while not finished and attempts < 600 and not progress:isCanceled() do
        attempts = attempts + 1
        Tasks.sleep(0.1)
    end
    -- Keep request alive until callback; no undocumented cancellation API.
    return data
end

Common.run('Prepara servizio', function(context)
    Common.token()
    local catalog, path, label = Common.catalog()
    assert(catalog:getTargetPhoto(), 'Seleziona le fotografie da importare in Lightroom.')
    local photos = catalog:getTargetPhotos()
    assert(#photos > 0, 'Nessuna fotografia selezionata.')
    local registration = Common.registration(path, true)
    local pendingFile = Common.file('imports', registration)
    local pending = Common.read(pendingFile)
    local title
    if pending and pending.manifest then
        local answer = Dialogs.confirm('Importazione sospesa', 'Riprendi «' .. pending.manifest.title .. '» nel catalogo ' .. label .. '.', 'Riprendi', 'Annulla', 'Nuovo servizio')
        if answer == 'other' then
            pending = nil
            title = askTitle(context, label, #photos)
            if not title then return end
        elseif answer ~= 'ok' then return end
    else
        title = askTitle(context, label, #photos)
        if not title then return end
    end
    Common.assertCatalog(path)
    local selected, objects = metadata(catalog, photos)
    assert(#selected > 0, 'La selezione non contiene fotografie supportate.')
    local manifest = pending and pending.manifest
    if manifest then
        assert(#selected == #manifest.photos, 'Per riprendere, seleziona esattamente le fotografie originali del servizio.')
        local current = {}
        for _, p in ipairs(selected) do current[p.id] = p end
        for _, p in ipairs(manifest.photos) do assert(current[p.id], 'La selezione per la ripresa contiene fotografie diverse.') end
    else
        manifest = { schema_version = 1, id = Common.newID(registration), title = title,
            catalog_id = registration, catalog_label = label, photos = selected }
        Common.write(pendingFile, { manifest = manifest })
    end
    local service = Common.request('POST', '/api/imports', manifest)
    local endpoint = '/api/services/' .. Common.key(manifest.id)
    if service.status == 'importing' then
        local progress = Progress { title = 'Preparazione anteprime Lightroom', functionContext = context }
        local missing, ready = 0, {}
        for _, p in ipairs(service.photos) do ready[p.id] = p.preview_ready end
        for index, item in ipairs(manifest.photos) do
            Common.assertCatalog(path)
            if progress:isCanceled() then return end
            if not ready[item.id] then
                local photo = objects[item.id]
                if photo:getRawMetadata('lastEditTime') == item.baseline_edit_time then
                    local jpeg = preview(photo, progress)
                    if progress:isCanceled() then return end
                    if jpeg and photo:getRawMetadata('lastEditTime') == item.baseline_edit_time then
                        Common.request('PUT', endpoint .. '/photos/' .. Common.key(item.id) .. '/preview', jpeg, 'image/jpeg')
                    else missing = missing + 1 end
                else missing = missing + 1 end
            end
            progress:setPortionComplete(index, #manifest.photos)
        end
        progress:done()
        if missing > 0 and Dialogs.confirm('Anteprime mancanti',
            tostring(missing) .. ' fotografie senza anteprima. Annulla per riprovare oppure chiudi l’importazione con le anteprime disponibili.',
            'Concludi importazione', 'Lascia in sospeso') ~= 'ok' then return end
        Common.request('POST', endpoint .. '/complete', '{}')
    end
    Common.write(pendingFile, { completed = true })
    Common.openBrowser()
end)
