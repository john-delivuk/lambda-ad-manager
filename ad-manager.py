import json
import boto3
import ldap3
import sys
import json
import socket

def add(instance):
	#print(instance)
	tags = lookup_aws_tags(instance)
	instance_ou = instance_ou = config['BaseDN']
	if lookup_tag_value(tags,'Application'):
		application = lookup_tag_value(tags,'Application')
		instance_ou = 'OU={0},{1}'.format(application,config['BaseDN'])
		if ou_exists(instance_ou, config['BaseDN']) == False:
			create_ou(instance_ou, config['BaseDN'])

	ssm_client = boto3.client('ssm')
	ssm_client.create_association(
		Name=config['SSMDocumentName'],
		InstanceId=instance,
		Parameters={
			'directoryId' : [config['DirectoryId']],
			'directoryName' : [config['DomainName']],
			'directoryOU' : [instance_ou],
			'dnsIpAddresses' : config['DnsServers']
	    }
    )
	return True

def ou_exists(ou_name, base_dn):
	conn = connect()
	obj_filter = '(&(Name={0})(objectCategory=organizationalUnit))'.format(ou_name)
	if conn.search(base_dn, obj_filter):
		conn.unbind()
		return True
	else:
		conn.unbind()
		return False

def create_ou(ou_name, base_dn):
	conn = connect()
	conn.add('OU={0},{1}'.format(ou_name, base_dn), 'organizationalUnit')
	conn.unbind()
	return True

def connect():
	auth_user_dn = config['UserName']
	auth_user_pw = config['Password']
	server = ldap3.Server(config['DomainName'], get_info='ALL')
	return ldap3.Connection(server, auth_user_dn, auth_user_pw, auto_bind=True)
	
def get_account_id(context):
  return context.invoked_function_arn.split(':')[4]

	
def get_config(file, env):
	try:
		target_config_set = json.load(open(file))[env]
	except ValueError:
		print('Unable to retrive the configuration set {0} from file {1}. Please verify the configuration set exists and the file is readable'.format(env,file))
	return target_config_set 

def delete(instance):
	conn = connect()
	base_dn = config['BaseDN']
	obj_filter = '(&(Name={0})(objectCategory=computer))'.format(instance)
	
	conn.search(base_dn, obj_filter)

	if len(conn.entries) == 1:
		target = conn.entries[0].entry_get_dn()
		conn.delete(target)
	elif len(conn.entries) < 1:
		print('No objects we\'re found that match the terminated instance, {0}.'.format(instance))
	else:
		print('More then one object was returned for your search, as a precaution this program will skip this instance, {0}.'.format(instance))

	conn.unbind()
	return True

def lookup_aws_tags (instanceid):
	ec2_resource = boto3.resource('ec2')
	return ec2_resource.Instance(instanceid).tags

def lookup_tag_value(tags, tagName):
	try:
		value_index = next(index for (index, d) in enumerate(tags) if d["Key"] == tagName)
	except StopIteration as err:
		return None
	else:
		return tags[value_index]['Value']

def lambda_handler(event, context):

	aws_account_id = get_account_id(context)
	global config 
	config = get_config('./config.json', aws_account_id)
	#print(socket.gethostbyname(config['DomainName']))
	for record in event['Records']:
		message_details = json.loads(record['Sns']['Message'])
		if message_details['Event'] == 'autoscaling:EC2_INSTANCE_LAUNCH':
			add(message_details['EC2InstanceId'])
		elif message_details['Event'] == 'autoscaling:EC2_INSTANCE_TERMINATE': 
			delete(message_details['EC2InstanceId'])
		else:
			print('Unable to read event')
			print(str(record))
	return True
