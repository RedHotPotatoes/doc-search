# create basic python container on alpine
FROM python:3.11.3-alpine

# set working directory
WORKDIR /app

# copy the project directory into the container
COPY . /app

# install git and bash
RUN apk add git
RUN apk add bash

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -e .

CMD ["python", "app.py"]
