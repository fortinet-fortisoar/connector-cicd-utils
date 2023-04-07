"""
Copyright start
Copyright (C) 2008 - 2023 Fortinet Inc.
All rights reserved.
FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
Copyright end
"""

import glob
import json
import shutil
import pathlib
from datetime import datetime
from connectors.core.connector import get_logger, ConnectorError
from connectors.cyops_utilities.files import save_file_in_env

logger = get_logger('cicd-utils')


def unzip_export_template(config, params, *args, **kwargs):
    env = kwargs.get('env', {})
    listOfFiles = list()
    target_filepath = '/tmp/' + datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    source_filepath = params.get('filepath')
    if '/tmp/' not in source_filepath:
        source_filepath = '/tmp/{0}'.format(source_filepath)
    shutil.unpack_archive(source_filepath, target_filepath, 'zip')

    search_target_filepath = target_filepath + '/**/*.*'
    for files in glob.iglob(search_target_filepath, recursive=True):
        listOfFiles.append(files)
    save_file_in_env(env, target_filepath)
    return {"filenames": listOfFiles}


def split_export_templates(config, params, *args, **kwargs):
    env = kwargs.get('env', {})
    prod_content_filepath = params.get('prod_content_filepath')
    export_template_recordset_path = pathlib.Path(prod_content_filepath)
    export_template_recordset_path = export_template_recordset_path.parent
    export_template_recordset_path.mkdir(parents=True, exist_ok=True)

    with open(params.get('prod_content_filepath'), 'w', encoding='utf-8') as f:
        json.dump(params.get('prod_content_json'), f, ensure_ascii=False, indent=4)

    with open(params.get('prod_settings_filepath'), 'w', encoding='utf-8') as f:
        json.dump(params.get('prod_settings_json'), f, ensure_ascii=False, indent=4)

    with open(params.get('dev_settings_filepath'), 'w', encoding='utf-8') as f:
        json.dump(params.get('dev_settings_json'), f, ensure_ascii=False, indent=4)

    oldFilePath = pathlib.Path(str(export_template_recordset_path) + '/export_templates0001.json')
    if oldFilePath.is_file():
        oldFilePath.unlink()

    unzip_filepath = params.get('unzip_filepath')
    if '/tmp/' not in unzip_filepath:
        unzip_filepath = '/tmp/{0}'.format(unzip_filepath)
    zip_filename = params.get('zip_filename')
    if '/tmp/' not in zip_filename:
        zip_filename = '/tmp/{0}'.format(zip_filename)
    shutil.make_archive(zip_filename, 'zip', unzip_filepath)

    save_file_in_env(env, zip_filename)
    return {"exportFileName": zip_filename}


operations = {
    'unzip_export_template': unzip_export_template,
    'split_export_templates': split_export_templates
}
