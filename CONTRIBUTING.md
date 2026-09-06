# Contributing

**Vendors:** if your gateway or SDK is on the scorecard and you think a scenario is wrong, open an issue with the scenario id and what you believe correct behaviour is, or send a pull request that changes `scenarios/catalogue.yaml`. Scenario changes are discussed in the open and bump the methodology version. Fixes you ship are credited in `CHANGELOG.md` and in the next scorecard.

**Everyone else:** new adapters (`failoverbench/adapters/`) and gateway configs (`gateways/`) are the most useful contributions. Run `python tests/test_smoke.py` before opening a pull request.

Please do not send pull requests that change a published result. Results are regenerated, never edited.
