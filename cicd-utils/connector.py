from connectors.core.connector import Connector
from connectors.core.connector import get_logger, ConnectorError
from .operations import operations

logger = get_logger('cicd-utils')


class CICDUtils(Connector):
    def execute(self, config, operation, params, *args, **kwargs):
        try:
            logger.info('In execute() Operation: {}'.format(operation))
            operation = operations.get(operation)
            return operation(config, params, *args, **kwargs)
        except Exception as err:
            logger.error('An exception occurred {}'.format(err))
            raise ConnectorError('{}'.format(err))
