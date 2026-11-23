# Configurazione di verifica per FlexForge (letta da verify.ps1).
@{
    Monolith      = 'flexforge\__init__.py'
    Sources       = @('flexforge')
    Runner        = 'tools\scripts\run_tests.ps1'
    ExpectedTotal = 232
    DiffPaths     = @('flexforge', 'tests')
    IndexOutput   = 'INDEX.md'
}
