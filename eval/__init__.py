"""The accuracy evaluation: a golden set, a scorer and a runner over two models.

Everything goes through `Agent.ask`, the same entry point the UI uses. Only
`eval.run` without `--fake` ever calls the Anthropic API.
"""
