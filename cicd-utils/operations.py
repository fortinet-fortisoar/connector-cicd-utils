"""
Copyright start
Copyright (C) 2008 - 2023 Fortinet Inc.
All rights reserved.
FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
Copyright end
"""
import shutil
import glob
from datetime import datetime
from connectors.core.connector import get_logger, ConnectorError
from connectors.cyops_utilities.files import save_file_in_env

logger = get_logger('cicd-utils')


def unzip_export_template(config, params, *args, **kwargs):
    env = kwargs.get('env', {})
    listOfFiles = list()
    target_filepath = '/tmp/' + datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    source_filepath = '/tmp/{0}'.format(params.get('filepath'))
    shutil.unpack_archive(source_filepath, target_filepath, 'zip')

    search_target_filepath = target_filepath + '/**/*.*'
    for files in glob.iglob(search_target_filepath, recursive=True):
        listOfFiles.append(files)
    save_file_in_env(env, target_filepath)
    return {"filenames": listOfFiles}


operations = {
    'unzip_export_template': unzip_export_template
}
