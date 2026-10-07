FROM postgres:16.15@sha256:65b16a8b326e0cfbdf33fa7e783f2a0cb352a61448616ccccfd616ef42aa0f65
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
