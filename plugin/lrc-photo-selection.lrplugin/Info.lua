return {
    LrSdkVersion = 12.0, LrSdkMinimumVersion = 12.0,
    LrToolkitIdentifier = 'com.ericcatta.lrc-photo-selection', LrPluginName = 'Selezione fotografie',
    LrLibraryMenuItems = {
        { title = 'Guida — da Lightroom alla selezione e ritorno', file = 'GuideMenu.lua' },
        { title = 'Mostra le candidate in Lightroom', file = 'Show.lua' },
        { title = 'Configura connessione locale', file = 'Configure.lua' },
        { title = 'Prepara servizio', file = 'Prepare.lua' },
        { title = 'Applica stelle', file = 'Apply.lua' },
    },
    VERSION = { major = 0, minor = 1, revision = 0 },
}
