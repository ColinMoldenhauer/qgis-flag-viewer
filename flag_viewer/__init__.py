def classFactory(iface):
    # Imported lazily so `flag_viewer.core` stays importable (e.g. for unit
    # tests) in environments that don't have the `qgis` package installed.
    from .flag_viewer_plugin import FlagViewerPlugin

    return FlagViewerPlugin(iface)
