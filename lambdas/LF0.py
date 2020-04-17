import json
import boto3
import base64
from botocore.vendored import requests
from boto3.dynamodb.conditions import Key, Attr

def getName(faceId) :
    dynamo_client = boto3.resource('dynamodb')
    visitors_table = dynamo_client.Table('visitors');
    response = visitors_table.query(KeyConditionExpression=Key('faceID').eq(faceId))
    nameInput = response['Items'][0]['name']
    return nameInput

def validate_otp(otp):
    if otp=="":
        return "Permission Denied"
    dynamo_client = boto3.resource('dynamodb')
    visitors_table = dynamo_client.Table('passcodes');
    response = visitors_table.query(IndexName='otp-index', KeyConditionExpression=Key('otp').eq(otp))
    if len(response['Items'])==0:
        return "Permission Denied"
    faceID_val = response['Items'][0]['faceId']
    return "Welcome "+getName(faceID_val)

def lambda_handler(event, context):
    print("THis is the event",event)
    otp = event['otp']
    # otp = "124"
    print("This is the otp :",otp)
    message = validate_otp(otp)
    return {
        'statusCode': 200,
        'body': message
    }
