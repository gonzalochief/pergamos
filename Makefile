.PHONY: install test run docker-up docker-down clean

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e '.[rag]'

test:
	.venv/bin/python -m pytest -q

run:
	CALIBRE_SERVER_URL=http://127.0.0.1:8080 .venv/bin/pergamos

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	rm -rf .venv .pergamos_index
