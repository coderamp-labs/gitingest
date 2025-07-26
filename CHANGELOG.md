# Changelog

## [0.2.0](https://github.com/coderamp-labs/gitingest/compare/v0.1.5...v0.2.0) (2025-07-26)


### ⚠ BREAKING CHANGES

* 
* 

### Features

* `include_submodules` option ([#313](https://github.com/coderamp-labs/gitingest/issues/313)) ([38c2317](https://github.com/coderamp-labs/gitingest/commit/38c23171a14556a2cdd05c0af8219f4dc789defd))
* add Tailwind CSS pipeline, tag-aware cloning & overhaul CI/CD ([#352](https://github.com/coderamp-labs/gitingest/issues/352)) ([b683e59](https://github.com/coderamp-labs/gitingest/commit/b683e59b5b1a31d27cc5c6ce8fb62da9b660613b))
* add Tailwind CSS pipeline, tag-aware cloning & overhaul CI/CD ([#352](https://github.com/coderamp-labs/gitingest/issues/352)) ([016817d](https://github.com/coderamp-labs/gitingest/commit/016817d5590c1412498b7532f6e854d20239c6be))
* **ci:** build Docker Image on PRs ([#382](https://github.com/coderamp-labs/gitingest/issues/382)) ([bc8cdb4](https://github.com/coderamp-labs/gitingest/commit/bc8cdb459482948c27e780b733ac7216d822529a))
* implement prometheus exporter ([#406](https://github.com/coderamp-labs/gitingest/issues/406)) ([1016f6e](https://github.com/coderamp-labs/gitingest/commit/1016f6ecb3b1b066d541d1eba1ddffec49b15f16))
* implement S3 integration for storing and retrieving digest files ([#427](https://github.com/coderamp-labs/gitingest/issues/427)) ([414e851](https://github.com/coderamp-labs/gitingest/commit/414e85189fb9055491530ba8c0665c798474451e))
* integrate Sentry for error tracking and performance monitoring ([#408](https://github.com/coderamp-labs/gitingest/issues/408)) ([590e55a](https://github.com/coderamp-labs/gitingest/commit/590e55a4d28a4f5c0beafbd12c525828fa79e221))
* Refactor backend to a rest api ([#346](https://github.com/coderamp-labs/gitingest/issues/346)) ([2b1f228](https://github.com/coderamp-labs/gitingest/commit/2b1f228ae1f6d1f7ee471794d258b13fcac25a96))
* **ui:** add inline PAT info tooltip inside token field ([#348](https://github.com/coderamp-labs/gitingest/issues/348)) ([2592303](https://github.com/coderamp-labs/gitingest/commit/25923037ea6cd2f8ef33a6cf1f0406c2b4f0c9b6))


### Bug Fixes

* enable metrics if env var is defined instead of being "True" ([#407](https://github.com/coderamp-labs/gitingest/issues/407)) ([fa2e192](https://github.com/coderamp-labs/gitingest/commit/fa2e192c05864c8db90bda877e9efb9b03caf098))
* fix docker container not launching ([#449](https://github.com/coderamp-labs/gitingest/issues/449)) ([998cea1](https://github.com/coderamp-labs/gitingest/commit/998cea15b4f79c5d6f840b5d3d916f83c8be3a07))
* frontend directory tree ([#363](https://github.com/coderamp-labs/gitingest/issues/363)) ([0fcf8a9](https://github.com/coderamp-labs/gitingest/commit/0fcf8a956f7ec8403a025177f998f92ddee96de0))
* gitignore and gitingestignore files are now correctly processed … ([#416](https://github.com/coderamp-labs/gitingest/issues/416)) ([74e503f](https://github.com/coderamp-labs/gitingest/commit/74e503fa1140feb74aa5350a32f0025c43097da1))
* Potential fix for code scanning alert no. 75: Uncontrolled data used in path expression ([#421](https://github.com/coderamp-labs/gitingest/issues/421)) ([9ceaf6c](https://github.com/coderamp-labs/gitingest/commit/9ceaf6cbbb0cdefbc79f78c5285406b9188b2d3d))
* reset pattern form when switching between include/exclude patterns ([#417](https://github.com/coderamp-labs/gitingest/issues/417)) ([7085e13](https://github.com/coderamp-labs/gitingest/commit/7085e138a74099b1df189b3bf9b8a333c8769380))
* temp files cleanup after ingest([#309](https://github.com/coderamp-labs/gitingest/issues/309)) ([e669e44](https://github.com/coderamp-labs/gitingest/commit/e669e444fa1e6130f3f22952dd81f0ca3fe08fa5))
* **ui:** update layout in PAT section to avoid overlaps & overflows ([#331](https://github.com/coderamp-labs/gitingest/issues/331)) ([b39ef54](https://github.com/coderamp-labs/gitingest/commit/b39ef5416c1f8a7993a8249161d2a898b7387595))
* **windows:** warn if Git long path support is disabled, do not fail ([b8e375f](https://github.com/coderamp-labs/gitingest/commit/b8e375f71cae7d980cf431396c4414a6dbd0588c))


### Documentation

* add GitHub Issue Form for bug reports ([#403](https://github.com/coderamp-labs/gitingest/issues/403)) ([4546449](https://github.com/coderamp-labs/gitingest/commit/4546449bbc1e4a7ad0950c4b831b8855a98628fd))
* add GitHub Issue Form for feature requests ([#404](https://github.com/coderamp-labs/gitingest/issues/404)) ([9b1fc58](https://github.com/coderamp-labs/gitingest/commit/9b1fc58900ae18a3416fe3cf9b5e301a65a8e9fd))
* Fix CLI help text accuracy ([#332](https://github.com/coderamp-labs/gitingest/issues/332)) ([fdcbc53](https://github.com/coderamp-labs/gitingest/commit/fdcbc53cadde6a5dc3c3626120df1935b63693b2))


### Code Refactoring

* centralize PAT validation, streamline repo checks & misc cleanup ([#349](https://github.com/coderamp-labs/gitingest/issues/349)) ([cea0edd](https://github.com/coderamp-labs/gitingest/commit/cea0eddce8c6846bc6271cb3a8d15320e103214c))
* centralize PAT validation, streamline repo checks & misc cleanup ([#349](https://github.com/coderamp-labs/gitingest/issues/349)) ([f8d397e](https://github.com/coderamp-labs/gitingest/commit/f8d397e66e3382d12f8a0ed05d291a39db830bda))
