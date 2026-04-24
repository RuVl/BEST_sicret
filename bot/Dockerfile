FROM python:3.12-slim
LABEL authors="SPb BEST"

# Set enviroment variables
ENV TZ="Europe/Moscow"
ENV PIP_ROOT_USER_ACTION=ignore

# Prepare project directory
WORKDIR /app

# Copy and install requirements
COPY ./requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project to directory
COPY . ./

# Run project
ENTRYPOINT ["python3", "run.py"]
