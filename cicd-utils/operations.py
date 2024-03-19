"""
Copyright start
MIT License
Copyright (c) 2024 Fortinet Inc
Copyright end
"""

import glob
import json
import shutil
import pathlib
from datetime import datetime
from connectors.core.connector import get_logger, ConnectorError
from connectors.cyops_utilities.files import save_file_in_env, download_file_from_cyops, upload_file_to_cyops
from connectors.cyops_utilities.crudhub import make_cyops_request
from .constants import *
from time import sleep

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
    return {'filenames': listOfFiles}


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
    save_file_in_env(env, zip_filename + '.zip')
    return {'exportFileName': zip_filename + '.zip'}


def export_fortisoar_template(config, params, *args, **kwargs):
    try:
        export_template_name = params.get('export_template_name')
        export_file_name = params.get('export_file_name')
        update_input_params = params.get('ignore_keys')
        # Get Export Template Step
        GET_EXPORT_TEMPLATE['env'] = kwargs.get('env', {})
        export_template = make_cyops_request(*args, **GET_EXPORT_TEMPLATE)

        # Update export_template if not exists
        template = {
            "name": "Export Templates",
            "type": "export_templates",
            "query": {
                "sort": [],
                "limit": 1,
                "logic": "AND",
                "filters": [
                    {
                        "type": "primitive",
                        "field": "name",
                        "value": export_template_name,
                        "operator": "eq",
                        "_operator": "eq"
                    }
                ],
                "__selectFields": ["uuid"]
            },
            "include": True,
            "whenExists": "replace",
            "moduleNotExists": True,
            "includeCorrelations": False
        }
        config_info = export_template['hydra:member']
        for item in config_info:
            if item["name"] == export_template_name and item.get('options') and not any((rs['type'] == 'export_templates') for rs in item['options'].get('recordSets', [])):
                item['options']['recordSets'].append(template)
        filtered_config_info = [entry for entry in config_info if entry.get('name') == export_template_name]
        if not filtered_config_info:
            raise ConnectorError(f"No matching entry found for '{export_template_name}'")
        uuid = filtered_config_info[0]['uuid']
        update_iri = f"/api/3/export_templates/{uuid}"
        make_cyops_request(iri=update_iri, method="PUT", body=filtered_config_info[0], *args, **kwargs)

        # Start export job
        export_job_uuid_iri = f"/api/export?fileName={export_file_name}.zip&template={uuid}"
        export_job = make_cyops_request(iri=export_job_uuid_iri, method="PUT", *args, **kwargs)
        export_job_uuid = export_job['jobUuid']
        export_job_iri = f'/api/3/export_jobs/{export_job_uuid}'

        # Monitor export job status
        for _ in range(10):
            export_job_details = make_cyops_request(iri=export_job_iri, method='GET', *args, **kwargs)
            if export_job_details['status'] == "Export Complete":
                break
            sleep(15)
        else:
            raise ConnectorError(f"Export job status: {export_job_details['status']}")

        # Download and unzip file
        file_iri = export_job_details["file"]['@id']
        zip_file = download_file_from_cyops(file_iri, *args, **kwargs)
        unzip_file = unzip_export_template(config={}, params={'filepath': zip_file['cyops_file_path']}, *args, **kwargs)

        # Modify export
        # Set parameters for modify_export function
        params = {
            "zip_filename": export_file_name,
            "unzip_filepath": f"/{unzip_file['filenames'][0].split('/')[1]}/{unzip_file['filenames'][0].split('/')[2]}",
            "dev_settings_json": [],
            "prod_content_json": [],
            "prod_settings_json": [],
            "dev_settings_filepath": f'/{unzip_file["filenames"][0].split("/")[1]}/{unzip_file["filenames"][0].split("/")[2]}/{export_file_name}/records/export_templates/Source Control - Development Settings.json',
            "prod_content_filepath": f'/{unzip_file["filenames"][0].split("/")[1]}/{unzip_file["filenames"][0].split("/")[2]}/{export_file_name}/records/export_templates/Source Control - Production Content.json',
            "prod_settings_filepath": f'/{unzip_file["filenames"][0].split("/")[1]}/{unzip_file["filenames"][0].split("/")[2]}/{export_file_name}/records/export_templates/Source Control - Production Settings.json'
        }
        for entry in config_info:
            if entry.get('name') == 'Source Control - Development Settings':
                params['dev_settings_json'].append(entry)
            elif entry.get('name') == 'Source Control - Production Content':
                params['prod_content_json'].append(entry)
            elif entry.get('name') == 'Source Control - Production Settings':
                params['prod_settings_json'].append(entry)
        split_export_templates(config={}, params=params, *args, **kwargs)

        # Remove the unnecessary diff
        if update_input_params:
            updated_zip_file = remove_keys_from_fortisoar_exported_zip(export_file_name, update_input_params, *args, **kwargs)
            logger.info("Updated zip file path: {0}".format(updated_zip_file))
        # Upload the modified file back to cyops
        uploaded_file = upload_file_to_cyops(file_path=f"{export_file_name}.zip", filename=f"{export_file_name}.zip", *args, **kwargs)
        return {"file_iri": uploaded_file['@id']}
    except Exception as err:
        logger.error(err)
        raise ConnectorError(err)


def import_fortisoar_template(config, params, *args, **kwargs):
    try:
        filename = params.get('filename')
        file_path = params.get('file_path')
        clone_zip_file = upload_file_to_cyops(file_path, filename=filename, *args, **kwargs)
        logger.info(" Creating import job")
        # Create import job
        import_job_iri = "/api/3/import_jobs"
        payload = {
            "status": "Draft",
            "file": {
                "@context": clone_zip_file['@context'],
                "@id": clone_zip_file['@id'],
                "@type": "File",
                "uuid": clone_zip_file['uuid'],
                "assignee": "",
                "id": clone_zip_file['uuid'],
                "filename": clone_zip_file['filename'],
                "mimeType": "application/zip"
            }
        }
        import_job = make_cyops_request(iri=import_job_iri, method="POST", body=payload, *args, **kwargs)
        logger.info(f"Job Created : {import_job}")
        # Start import job
        logger.info("starting job ")
        import_job_uuid = import_job['uuid']
        import_job_iri_uuid = f'/api/import/{import_job_uuid}'
        import_job_details = make_cyops_request(iri=import_job_iri_uuid, method='GET', *args, **kwargs)

        logger.info(f"Job details: {import_job_details}")
        # Monitor import job status
        logger.info("Monitor export job status")
        import_job_iri = f'/api/3/import_jobs/{import_job_uuid}?__selectFields=errorMessage,status,progressPercent,file,currentlyImporting,options'
        for _ in range(5):
            import_job_details = make_cyops_request(iri=import_job_iri, method='GET', *args, **kwargs)
            logger.info(f"Monitor export job status: {import_job_details['status']}")
            if import_job_details['status'] == "Reviewing":
                break
            sleep(5)
        else:
            logger.error(f"Import job status: {import_job_details['status']}")
            raise ConnectorError(f"Import job status is not updated. current status is {import_job_details['status']}")

        # Update mport Job
        logger.info("Updating import job")
        iri = f'/api/3/import_jobs/{import_job_details["uuid"]}'
        playbooks = []
        if import_job_details["options"].get("playbooks"):
            for item in import_job_details["options"]["playbooks"]["values"]["collections"]["values"]:
                if item.get("mergeType") == "merge_append":
                    item["mergeType"] = "merge_replace"
                    playbooks.append(item)
            import_job_details["options"]["playbooks"]["values"]["collections"]["values"] = playbooks
        res = make_cyops_request(iri=iri, method='PUT', body=import_job_details, *args, **kwargs)
        logger.debug(f"Updated Import Job: {res}")

        # Import Zip File
        logger.info("Importing zip file")
        return make_cyops_request(iri=import_job_iri_uuid, method='PUT', body=import_job_details, *args, **kwargs)
    except Exception as err:
        logger.error(err)
        raise ConnectorError(err)


def remove_keys_from_fortisoar_exported_zip(export_file_name, update_input_params, *args, **kwargs):

    def load_json_file_data(filepath):
        with open(filepath, 'r', encoding='utf-8') as json_file:
            logger.info("Reading file {0}".format(filepath))
            data = json.load(json_file)
        return data

    def write_data_into_json_file(filepath, data):
        with open(filepath, 'w', encoding='utf-8') as file:
            logger.info("Writing file {0}".format(filepath))
            json.dump(data, file, ensure_ascii=False, indent=4)

    # Update data for each operation
    def update_data(json_data, op):
        try:
            temp = json_data
            if op.get('key_path'):
                key_path_elements = op.get('key_path').split('.')
                if key_path_elements:
                    for key in key_path_elements:
                        temp = temp.get(key)
            if op.get('key_type') == 'dict':
                for k in op.get('keys_to_remove'):
                    temp.pop(k) if k in temp.keys() else logger.warning("{0} key not found key_path {1}".format(key, op.get('key_path')))
            elif op.get('key_type') == 'list':
                key_to_compare = op.get('key_to_compare')
                values_to_remove = op.get('values_to_remove')
                keys_to_remove = op.get('keys_to_remove')
                filtered_list = []
                for obj in temp:
                    if key_to_compare and values_to_remove:
                        if obj.get(key_to_compare) in values_to_remove:
                            continue
                    if keys_to_remove:
                        for k in keys_to_remove:
                            obj.pop(k) if k in obj.keys() else logger.warning("{0} key not found key_path {1}".format(k, op.get('key_path')))
                    filtered_list.append(obj)
                if not op.get('key_path'):
                    return filtered_list
                key = key_path_elements.pop()
                temp = json_data
                for k in key_path_elements:
                    temp = temp.get(k)
                temp[key] = filtered_list
            return json_data
        except Exception as err:
            logger.exception("Error occurred while updating {0} file for following operation: {1}.\nError: {2}".format(param.get("file_path"), op, str(err)))
            return json_data

    env = kwargs.get('env', {})
    file_path = f'/tmp/{export_file_name}'
    shutil.unpack_archive(f'{file_path}.zip', file_path, 'zip')
    save_file_in_env(env, file_path)
    for param in update_input_params:
        try:
            # load file
            data = load_json_file_data(f'{file_path}/{export_file_name}/{param.get("file_path").strip("/")}')
            # Process all operations
            if data:
                for operation in param.get('operations'):
                    if not isinstance(data, (list, dict)):
                        logger.error("Invalid type '{0}' to update {1} file.".format(type(data), param.get('file_path')))
                        raise ConnectorError("Invalid type '{0}' to update {1} file.".format(type(data), param.get('file_path')))
                    elif isinstance(data, dict) or (not operation.get('key_path') and operation.get('key_type') == 'list'):
                        updated_data = update_data(data, operation)
                    else:
                        updated_data = []
                        for json_data in data:
                            u_data = update_data(json_data, operation)
                            updated_data.append(u_data)
                # Write updated file
                write_data_into_json_file(f'{file_path}/{export_file_name}/{param.get("file_path").strip("/")}', updated_data)
        except Exception as error:
            logger.exception("Error occurred for {0} file. Error: {1}".format(param.get('file_path'), str(error)))
    zip_file = shutil.make_archive(file_path, 'zip', file_path)
    save_file_in_env(env, "{0}.zip".format(file_path))
    return zip_file


operations = {
    'unzip_export_template': unzip_export_template,
    'split_export_templates': split_export_templates,
    'export_fortisoar_template': export_fortisoar_template,
    'import_fortisoar_template': import_fortisoar_template
}