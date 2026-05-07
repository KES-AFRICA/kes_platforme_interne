#lancer le virtual env
source .venv/bin/activate

#Initialiser Alembic
alembic init -t async alembic

#lancer le backend
uvicorn app.main:app --reload
