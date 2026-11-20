"""Contract 2.2 month precision; filter bounds never become claimed event days."""
import calendar,re
from copy import deepcopy
from datetime import date
from jsonschema import Draft202012Validator,FormatChecker

FIELDS=('as_of','valid_from','valid_to')

def bounds(value,precision='day'):
    if precision=='month':
        if not isinstance(value,str) or not re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])',value):
            raise ValueError('Invalid month')
        y,m=map(int,value.split('-'));first=date(y,m,1)
        return first.isoformat(),date(y,m,calendar.monthrange(y,m)[1]).isoformat()
    if precision!='day' or not isinstance(value,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):
        raise ValueError('Invalid day/precision')
    day=date.fromisoformat(value).isoformat()
    return day,day

def validate_temporal(temporal,allow_month=False):
    allowed=set(FIELDS)|({f+'_precision' for f in FIELDS} if allow_month else set())
    if set(temporal)-allowed:raise ValueError('Unknown temporal field')
    for field in FIELDS:
        value=temporal.get(field);precision=temporal.get(field+'_precision','day')
        if value is None:
            if field+'_precision' in temporal:raise ValueError('Precision without temporal value')
            continue
        if precision=='month' and not allow_month:raise ValueError('Month precision requires contract 2.2.0')
        bounds(value,precision)
    if temporal.get('valid_from') and temporal.get('valid_to'):
        start=bounds(temporal['valid_from'],temporal.get('valid_from_precision','day'))[0]
        end=bounds(temporal['valid_to'],temporal.get('valid_to_precision','day'))[1]
        if start>end:raise ValueError('Reversed interval')

def extended_validator(schema):
    schema=deepcopy(schema);schema['properties']['schema_version']={'const':'2.2.0'}
    temporal_object=schema['$defs']['relation']['properties']['temporal']
    temporal=temporal_object['properties'];conditions=[]
    month_pattern=r'^[0-9]{4}-(?:0[1-9]|1[0-2])$'
    for field in FIELDS:
        temporal[field]={'anyOf':[{'type':'null'},{'type':'string','format':'date'},
                                   {'type':'string','pattern':month_pattern}]}
        temporal[field+'_precision']={'enum':['day','month']}
        conditions.append({'if':{'required':[field],'properties':{field:{'type':'string','pattern':month_pattern}}},
                           'then':{'required':[field+'_precision'],'properties':{field+'_precision':{'const':'month'}}}})
        for precision,rule in [('month',{'type':'string','pattern':month_pattern}),('day',{'type':'string','format':'date'})]:
            conditions.append({'if':{'required':[field+'_precision'],'properties':{field+'_precision':{'const':precision}}},
                               'then':{'required':[field],'properties':{field:rule}}})
    temporal_object['allOf']=conditions
    return Draft202012Validator(schema,format_checker=FormatChecker())

def month_supported(value,quote):
    bounds(value,'month');year,month=value.split('-');m=int(month)
    return bool(re.search(rf'(?<![\d/.-]){re.escape(value)}(?![\d-])|(?<![\d/.-])0?{m}/{year}(?!\d)|\btháng\s+0?{m}\s+năm\s+{year}\b',quote))
