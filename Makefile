# bin/kurt, and the framework's own tests.
#
#   make            build bin/kurt
#   make install    link it into $(PREFIX)/bin (~/.local/bin), next to iyi
#   make test       the tests on SQLite (in memory)
#   make test-pg    the model and fixture tests on PostgreSQL: PG_URL=postgres://user@host:port/db
IYI ?= iyi
PG_URL ?= postgres://localhost/kurt_test
PREFIX ?= $(HOME)/.local

bin/kurt: cmd/kurt.iyi $(wildcard *.iyi)
	@mkdir -p bin
	$(IYI) build cmd/kurt.iyi -o bin/kurt

# A link, not a copy: kurt finds this checkout through it (the logo new
# applications get, KURT_PATH's default for working on Kurt).
install: bin/kurt
	@mkdir -p $(PREFIX)/bin
	ln -sf $(CURDIR)/bin/kurt $(PREFIX)/bin/kurt
	@echo "kurt -> $(PREFIX)/bin/kurt"

test:
	DATABASE_URL="sqlite3:%3Amemory%3A?max_pool_size=1" $(IYI) test -p 1

test-pg:
	DATABASE_URL="$(PG_URL)" $(IYI) run test/model_test.iyi
	DATABASE_URL="$(PG_URL)" $(IYI) run test/fixtures_test.iyi

.PHONY: install test test-pg
