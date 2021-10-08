import logging, os, datetime


def get_logger(
        application_path: str, local_time: datetime.datetime
) -> logging.getLogger:
    # Create the logs folder if it's not created yet
    logs_folder_name = 'logs for the past 20 days'
    logs_path = os.path.join(application_path, logs_folder_name)
    if logs_folder_name not in os.listdir(application_path):
        os.mkdir(logs_path)

    # Create the logging object
    report_name = os.path.join(logs_path, 'log ' + local_time.strftime('%Y-%m-%d %H-%M-%S') + '.txt')
    logging.basicConfig(filename=report_name, level=logging.INFO, format=' %(asctime)s -  %(levelname)s -  %(message)s')

    # Remove the old logs
    for fileName in os.listdir(logs_path):
        try:
            log_date = datetime.datetime.strptime(fileName[4:-4], '%Y-%m-%d %H-%M-%S')
            if log_date < (local_time - datetime.timedelta(days=20)):
                os.remove(os.path.join(logs_path, fileName))
        except:
            continue

    return logging.getLogger()