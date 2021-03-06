define PROJECT_HELP_MSG
Usage:
    make help                   show this message
    make build                  build docker image
    make run					run container
    make start-scheduler		start Dask scheduler in the container
    make start-workers			start Dask workers in the container
    make run-pipeline			run style transfer model in Dask
    make stop					stop the container and remove
endef
export PROJECT_HELP_MSG
PWD:=$(shell pwd)
NAME:=dask-styletransfer # Name of running container

image_name:=masalvar/dask-styletransfer
local_code_volume:=-v $(PWD):/workspace
tag:=version_.001
docker_exec:=docker exec -it $(NAME)
scheduler:=127.0.0.1:8786
log_config:=style_transfer/logging.ini
model_dir:=/models/saved_models
style:=mosaic

# MODIFY THESE
data_volume=-v /mnt/pipelines:/data
filepath:=/data/people
output_path:=/data/output


help:
	echo "$$PROJECT_HELP_MSG" | less

build: # Docker container for local control plane
	docker build -t $(image_name) -f Docker/dockerfile Docker

run:# Run docker locally for dev and control
	docker run --runtime=nvidia \
			   $(local_code_volume) \
	           $(data_volume) \
			   --name $(NAME) \
	           -p 8787:8787 \
	           -d \
	           -e PYTHONPATH=/workspace:$$PYTHONPATH \
	           -it $(image_name)

bash:
	$(docker_exec) bash


start-scheduler:
	docker exec -it -d $(NAME) tmux new -s dask -d \; \
									neww -d -n scheduler dask-scheduler

start-workers:
	docker exec -it -d  $(NAME) tmux \
		neww -d -n worker1 "CUDA_VISIBLE_DEVICES=0 dask-worker ${scheduler} --nprocs 1 --nthreads 1 --resources 'GPU=1'" \; \
		neww -d -n worker2 "CUDA_VISIBLE_DEVICES=1 dask-worker ${scheduler} --nprocs 1 --nthreads 1 --resources 'GPU=1'" \; \
		neww -d -n worker3 "CUDA_VISIBLE_DEVICES=2 dask-worker ${scheduler} --nprocs 1 --nthreads 1 --resources 'GPU=1'" \; \
		neww -d -n worker4 "CUDA_VISIBLE_DEVICES=3 dask-worker ${scheduler} --nprocs 1 --nthreads 1 --resources 'GPU=1'" \;

stop-workers:
	docker exec -it -d  $(NAME) tmux \
		killw -t worker1 \; \
		killw -t worker2 \; \
		killw -t worker3 \; \
		killw -t worker4 \;


run-pipeline:
	docker exec -e LOG_CONFIG=$(log_config) -it $(NAME) python style_transfer/style_transfer_local.py ${scheduler} ${model_dir} ${style} ${filepath} ${output_path}

stop:
	docker stop $(NAME)
	docker rm $(NAME)

.PHONY: help build run bash stop