import logging.config
import fire
from style_transfer import dask_pipeline


def run(scheduler_address, model_dir, style, filepath, output_path):
    logging.config.fileConfig(os.getenv("LOG_CONFIG", "logging.ini"))

    dask_pipeline.start(model_dir, style, filepath, output_path, scheduler_address)


if __name__ == "__main__":
    fire.Fire(run)
