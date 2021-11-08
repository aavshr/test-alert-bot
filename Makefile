format:
	poetry run isort main.py
	poetry run black main.py

lint:
	poetry run isort --check --diff main.py
	poetry run isort --check --diff main.py

generate-requirements:
	poetry export -o requirements.txt --without-hashes
