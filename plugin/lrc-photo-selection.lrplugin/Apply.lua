local Common = require 'Common'
local Binding = import 'LrBinding'
local Dialogs = import 'LrDialogs'
local Progress = import 'LrProgressScope'
local View = import 'LrView'

local Selection = require 'Selection'
local Guide = require 'Guide'

local function confirmPlan(context, service, plan, label, byID)
    local properties = Binding.makePropertyTable(context)
    properties.xmpChecked = false
    local lines = {}
    for _, item in ipairs(plan.items) do
        local filename = byID[item.photo_id].filename or item.photo_id
        lines[#lines + 1] = filename:gsub('%c', ' ') .. ' [' .. item.photo_id .. '] · 0 → 1'
    end
    properties.operations = table.concat(lines, '\n')
    local view = View.osFactory()
    local answer = Dialogs.presentModalDialog {
        title = 'Conferma applicazione stelle',
        contents = view:column {
            bind_to_object = properties,
            view:static_text { title = 'Catalogo: ' .. label },
            view:static_text { title = 'Servizio: ' .. service.title .. ' (revisione ' .. plan.revision .. ')' },
            view:static_text { title = 'Piano ' .. plan.batch_id .. ' · ' .. #plan.items .. ' operazioni' },
            view:scrolled_view { width = 620, height = 180, view:edit_field { value = View.bind 'operations', width_in_chars = 72, height_in_lines = #lines + 1, enabled = false } },
            view:static_text { title = '1. In Impostazioni catalogo → Metadati verifica che la scrittura automatica XMP sia disattivata.' },
            view:static_text { title = '2. La casella qui sotto attesta la verifica: non modifica le preferenze di Lightroom.' },
            view:checkbox { title = 'Ho verificato che la scrittura automatica delle modifiche in XMP è disattivata.', value = View.bind 'xmpChecked' },
            Guide.button(),
        }, actionBinding = { enabled = { bind_to_object = properties, key = 'xmpChecked' } }, actionVerb = 'Applica stelle', cancelVerb = 'Annulla',
    }
    if answer ~= 'ok' then return false end
    if properties.xmpChecked ~= true then
        Dialogs.message('Verifica XMP necessaria', 'Nessuna stella applicata. Verifica la scrittura automatica XMP in Impostazioni catalogo → Metadati, poi riapri Applica stelle e spunta l’attestazione nel plugin.', 'warning')
        return false
    end
    return true
end

local function result(item, status, reason, before, after)
    return {photo_id = item.photo_id, status = status, reason = reason, before = before, after = after}
end

local function applyOne(catalog, path, marker, outcomePath, plan, item, photo, progress)
    local outcome, wrote
    local gate = catalog:withWriteAccessDo('Selezione fotografie: assegna una stella', function()
        Common.assertCatalog(path)
        outcome = Common.read(outcomePath)
        if outcome then return end
        local prior = Common.read(marker)
        if prior then
            if prior.batch_id == plan.batch_id then
                outcome = result(item, 'uncertain', 'Tentativo precedente senza esito verificato; stella non riapplicata.')
            else
                outcome = result(item, 'skipped', 'Questa fotografia ha già avuto un tentativo di valutazione.')
            end
            return
        end
        if progress:isCanceled() then
            outcome = result(item, 'skipped', 'Applicazione interrotta prima di questa foto.')
            return
        end
        if not Selection.matches(photo, item) then
            outcome = result(item, 'conflict', 'Identificativo Lightroom non trovato o ambiguo.')
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
    local sid = Selection.chooseService(context, registration, label, {
        title = 'Scegli il servizio', action = 'Mostra piano', statuses = {ready = true, applying = true},
    })
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
    if not confirmPlan(context, service, plan, label, byID) then return end
    Common.assertCatalog(path)
    local claimed = Common.request('POST', endpoint .. '/rating-plan/claim', {batch_id = batch})
    assert(claimed.ok == true, 'Il piano non è stato riservato dal backend.')
    local photos = Selection.identify(catalog, plan.items)
    local progress = Progress { title = 'Applicazione valutazioni Lightroom', functionContext = context }
    local results, applied = {}, 0
    for index, item in ipairs(plan.items) do
        Common.assertCatalog(path)
        local outcomePath = Common.file('batch-' .. batch, item.photo_id)
        local outcome = Common.read(outcomePath)
        if not outcome then
            local marker = Common.file('rating-' .. registration, item.photo_id)
            outcome = applyOne(catalog, path, marker, outcomePath, plan, item, photos[item.photo_id], progress)
            local recorded = Common.read(outcomePath)
            if recorded then outcome = recorded else Common.write(outcomePath, outcome) end
        end
        results[#results + 1] = outcome
        if outcome.status == 'applied' then applied = applied + 1 end
        progress:setPortionComplete(index, #plan.items)
    end
    progress:done()
    Common.request('POST', endpoint .. '/rating-receipts', {batch_id = batch, results = results})
    local skipped, review = 0, 0
    for _, outcome in ipairs(results) do
        if outcome.status == 'skipped' then skipped = skipped + 1 end
        if outcome.status == 'conflict' or outcome.status == 'uncertain' then review = review + 1 end
    end
    local complete = applied == #plan.items
    Dialogs.message(complete and 'Applicazione completata' or 'Applicazione da verificare',
        tostring(applied) .. ' stelle applicate su ' .. #plan.items .. ' previste; '
        .. skipped .. ' saltate; ' .. review .. ' da verificare.\n'
        .. 'Consulta Esito nella web app per la ricevuta. Per vedere le candidate: Libreria → Extra plug-in → Mostra le candidate in Lightroom.',
        complete and 'info' or 'warning')
end)
