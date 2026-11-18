local Common = require 'Common'
local Binding = import 'LrBinding'
local Dialogs = import 'LrDialogs'
local Progress = import 'LrProgressScope'
local View = import 'LrView'

local function chooseService(context, registration, label)
    local options = {}
    for _, item in ipairs(Common.request('GET', '/api/services')) do
        if item.catalog_id == registration and (item.status == 'ready' or item.status == 'applying') then
            options[#options + 1] = {title = item.title, value = item.id}
        end
    end
    assert(#options > 0, 'Nessun servizio pronto associato a questo catalogo.')
    local properties = Binding.makePropertyTable(context)
    properties.selected = options[1].value
    local view = View.osFactory()
    local answer = Dialogs.presentModalDialog {
        title = 'Scegli il servizio',
        contents = view:column {
            bind_to_object = properties,
            view:static_text { title = 'Catalogo: ' .. label },
            view:popup_menu { value = View.bind 'selected', items = options },
        }, actionVerb = 'Mostra piano', cancelVerb = 'Annulla',
    }
    return answer == 'ok' and Common.key(properties.selected) or nil
end

local function confirmPlan(context, service, plan, label)
    local properties = Binding.makePropertyTable(context)
    properties.xmpChecked = false
    local view = View.osFactory()
    local answer = Dialogs.presentModalDialog {
        title = 'Conferma applicazione stelle',
        contents = view:column {
            bind_to_object = properties,
            view:static_text { title = 'Catalogo: ' .. label },
            view:static_text { title = 'Servizio: ' .. service.title .. ' (revisione ' .. plan.revision .. ')' },
            view:static_text { title = 'Il piano mostrato nella web app prevede fino a ' .. #plan.items .. ' passaggi da zero a una stella.' },
            view:static_text { title = 'Controlla Impostazioni catalogo → Metadati prima di confermare.' },
            view:checkbox { title = 'Ho verificato che la scrittura automatica delle modifiche in XMP è disattivata.', value = View.bind 'xmpChecked' },
        }, actionVerb = 'Applica stelle', cancelVerb = 'Annulla',
    }
    if answer ~= 'ok' then return false end
    assert(properties.xmpChecked == true, 'Applicazione bloccata: l’impostazione XMP non è stata verificata.')
    return true
end

local function matches(photo, item)
    return photo and photo.localIdentifier == item.local_id and photo:getRawMetadata('uuid') == item.uuid
end

local function identify(catalog, items)
    local photos, missing = {}, {}
    for _, item in ipairs(items) do
        local photo = catalog:findPhotoByUuid(item.uuid)
        if matches(photo, item) then photos[item.photo_id] = photo else missing[item.local_id] = item end
    end
    if next(missing) then
        for _, photo in ipairs(catalog:getAllPhotos()) do
            local item = missing[photo.localIdentifier]
            if item and matches(photo, item) then photos[item.photo_id] = photo end
        end
    end
    return photos
end

local function result(item, status, reason, before, after)
    return {photo_id = item.photo_id, status = status, reason = reason, before = before, after = after}
end

local function applyOne(catalog, path, marker, plan, item, photo)
    local prior = Common.read(marker)
    if prior then
        if prior.batch_id == plan.batch_id then return result(item, 'uncertain', 'Tentativo precedente senza esito verificato; stella non riapplicata.') end
        return result(item, 'skipped', 'Questa fotografia ha già avuto un tentativo di valutazione.')
    end
    if not matches(photo, item) then return result(item, 'conflict', 'Identificativo Lightroom non trovato o ambiguo.') end
    local outcome, wrote
    local gate = catalog:withWriteAccessDo('Selezione fotografie: assegna una stella', function()
        Common.assertCatalog(path)
        if not matches(photo, item) then
            outcome = result(item, 'conflict', 'Identificativo Lightroom non più corrispondente.')
            return
        end
        local current = photo:getRawMetadata('rating') or 0
        local edited = photo:getRawMetadata('lastEditTime')
        if current ~= 0 or type(edited) ~= 'number' or edited ~= item.expected_edit_time then
            outcome = result(item, 'conflict', 'Valutazione o data di modifica diversa dallo stato importato.', current, current)
            return
        end
        Common.write(marker, {batch_id = plan.batch_id})
        photo:setRawMetadata('rating', 1)
        wrote = true
    end, {timeout = 5})
    if gate ~= 'executed' then return result(item, 'skipped', 'Accesso di scrittura al catalogo non disponibile.') end
    if not wrote then return assert(outcome, 'Esito di valutazione non disponibile.') end
    local newRating = photo:getRawMetadata('rating') or 0
    if newRating == 1 then return result(item, 'applied', 'Una stella confermata dopo la modifica.', 0, 1) end
    return result(item, 'uncertain', 'Stella non verificabile dopo la modifica.', 0, newRating)
end

Common.run('Applica stelle', function(context)
    local catalog, path, label = Common.catalog()
    local registration = Common.registration(path, false)
    local sid = chooseService(context, registration, label)
    if not sid then return end
    local endpoint = '/api/services/' .. sid
    local service = Common.request('GET', endpoint)
    local plan = Common.request('GET', endpoint .. '/rating-plan/latest')
    assert(plan.schema_version == 1 and plan.service_id == sid and plan.catalog_id == registration
        and plan.revision == service.revision, 'Il piano non corrisponde al catalogo o alla revisione attuale.')
    local batch = Common.key(plan.batch_id)
    local byID, seen = {}, {}
    for _, photo in ipairs(service.photos) do byID[photo.id] = photo end
    for _, item in ipairs(plan.items) do
        local id = Common.key(item.photo_id)
        local imported = byID[id]
        assert(not seen[id] and imported and imported.uuid == item.uuid and imported.local_id == item.local_id
            and imported.baseline_rating == 0 and item.expected_rating == 0 and item.target_rating == 1
            and type(item.expected_edit_time) == 'number' and imported.baseline_edit_time == item.expected_edit_time,
            'Il piano contiene un’operazione non valida.')
        seen[id] = true
    end
    if #plan.items == 0 then
        Dialogs.message('Nessuna modifica', 'Il piano non contiene valutazioni da applicare.', 'info')
        return
    end
    if not confirmPlan(context, service, plan, label) then return end
    Common.assertCatalog(path)
    local claimed = Common.request('POST', endpoint .. '/rating-plan/claim', {batch_id = batch})
    assert(claimed.ok == true, 'Il piano non è stato riservato dal backend.')
    local photos = identify(catalog, plan.items)
    local progress = Progress { title = 'Applicazione valutazioni Lightroom', functionContext = context }
    local results, applied = {}, 0
    for index, item in ipairs(plan.items) do
        Common.assertCatalog(path)
        local outcomePath = Common.file('batch-' .. batch, item.photo_id)
        local outcome = Common.read(outcomePath)
        if not outcome then
            local marker = Common.file('rating-' .. registration, item.photo_id)
            if progress:isCanceled() and not Common.read(marker) then outcome = result(item, 'skipped', 'Applicazione interrotta prima di questa foto.')
            else outcome = applyOne(catalog, path, marker, plan, item, photos[item.photo_id]) end
            Common.write(outcomePath, outcome)
        end
        results[#results + 1] = outcome
        if outcome.status == 'applied' then applied = applied + 1 end
        progress:setPortionComplete(index, #plan.items)
    end
    progress:done()
    Common.request('POST', endpoint .. '/rating-receipts', {batch_id = batch, results = results})
    Dialogs.message('Applicazione completata', tostring(applied) .. ' valutazioni applicate su '
        .. #plan.items .. ' previste. Consulta la ricevuta nella web app.', 'info')
end)
