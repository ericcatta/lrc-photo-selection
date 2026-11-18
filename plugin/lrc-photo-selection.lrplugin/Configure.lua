local Common = require 'Common'
local Binding = import 'LrBinding'
local Dialogs = import 'LrDialogs'
local View = import 'LrView'
Common.run('Configura connessione locale', function(context)
    local properties = Binding.makePropertyTable(context)
    properties.token = ''
    local view = View.osFactory()
    local answer = Dialogs.presentModalDialog {
        title = 'Connessione alla web app locale',
        contents = view:column {
            bind_to_object = properties,
            view:static_text { title = 'Incolla il token mostrato dal comando di avvio del backend.' },
            view:password_field { value = View.bind 'token', width_in_chars = 48 },
        }, actionVerb = 'Collega', cancelVerb = 'Annulla',
    }
    if answer ~= 'ok' then return end
    local token = properties.token:match('^%s*(.-)%s*$')
    Common.request('GET', '/api/services', nil, nil, token)
    Common.saveToken(token)
    Common.openBrowser(token)
end)
