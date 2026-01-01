#
SITE_NAME=SITE_NAME ## e.g., YYNET
SITE_DOMAIN=SITE_DOMAIN ## e.g., localhost:8000
EMAIL=EMAIL              ## e.g., webmaster@example.com

all:
	python manage.py makemigrations --no-color 
	python manage.py migrate --no-color
	@echo
	@echo e.g.
	@echo "# python contrib/generate_secretkey.py >>config/.secrets.toml"
	@echo "# python manage.py update_site --name ${SITE_NAME} --domain ${SITE_DOMAIN}"
	@echo "# python manage.py createsuperuser --no-input --email ${EMAIL}"
	@echo "# python manage.py setup_test_data --no-color"

check:
	isort . --check | cat
	black . --check | cat
	flake8 --exclude migrations .
	mypy .

format:
	isort .
	black . | cat

test:
	python manage.py test

dumpdata:
	python manage.py dumpdata --exclude auth.permission --exclude contenttypes >dumpdata.json

loaddata:
	python manage.py loaddata dumpdata.json

clean:
	find . -type d -name __pycache__ | xargs rm -rf

distclean: clean
	rm -f db.sqlite3 
	find . -path '*/migrations/*.py' -not -name __init__.py | xargs rm -rf
