# Configurazione di verifica per FlexForge (letta da verify.ps1).
@{
    Monolith      = 'flexforge\__init__.py'
    Sources       = @('flexforge')
    Runner        = '.opencode\scripts\run_tests.ps1'
    ExpectedTotal = 203
    DiffPaths     = @('flexforge', 'tests')
    IndexOutput   = 'INDEX.md'
}
