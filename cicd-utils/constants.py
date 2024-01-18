"""
Copyright start
MIT License
Copyright (c) 2024 Fortinet Inc
Copyright end
"""
GET_EXPORT_TEMPLATE = {
        'iri': '/api/query/export_templates?$export=true&$limit=2147483647',
        'body': {
            "logic": "AND",
            "filters": [
                {
                    "field": "name",
                    "operator": "like",
                    "value": "%Source Control%"
                }
            ]
        },
        'method': 'POST'
    }