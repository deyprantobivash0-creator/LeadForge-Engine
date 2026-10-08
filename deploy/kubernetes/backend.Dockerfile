FROM leadforge-backend:5h-l-base
COPY deploy/staging/ /staging/
COPY deploy/kubernetes/check_schema.py /kubernetes/check_schema.py
