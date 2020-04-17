import json
import boto3
from botocore.vendored import requests
from boto3.dynamodb.conditions import Key, Attr
import time
import random
import math

def copy_to_photos_bucket(objKey):
    s3 = boto3.resource('s3')
    copy_source = {
      'Bucket': 'rekframebucket',
      'Key': "frame.jpg"
    }
    photoname = objKey
    visitors_photos = s3.Bucket('rekognition-photos')
    visitors_photos.copy(copy_source, photoname, {'ACL' : 'public-read'})


def generateOTP() : 
    digits = "0123456789"
    OTP = "" 
    for i in range(6) : 
        OTP += digits[math.floor(random.random() * 10)] 
    return OTP

def insert_into_passcodes(faceId, otp):
    dynamo_client = boto3.resource('dynamodb')
    otp_table = dynamo_client.Table('passcodes')
    exists = otp_table.query(IndexName='faceId-index', KeyConditionExpression=Key('faceId').eq(faceId))
    if len(exists['Items'])!=0:
        return False;
    otp_table.put_item(
        Item={
            "ID": str(time.time()),
            "faceId" : faceId,
            "otp" : otp,
            "ttl" : int(time.time() + 300)
            }
    )
    return True
    
def send_otp(otp, number):
    sns = boto3.client("sns")
    msg = "Your One Time Password is " + str(otp) + " Enter it in this link.  " + "http://virtual-door-files.s3-website-us-west-2.amazonaws.com/otp_validate/"
    sub = "Your Smart Gate OTP"
    response = sns.publish(PhoneNumber=number, Message=msg,Subject=sub) 
    print("sns sent" + json.dumps(response))
    
def lambda_handler(event, context):
    name = event['name']
    # name = "Anjan"
    number = event['number'] 
    # number = "3478818075"
    if not number.startswith("+1"):
        number = "+1"+number
    print(name, number)
    # name = 'Anjan'
    # number = '+13478818075'

    collectionId = 'rekVideoBlog'
    frame_name = "frame.jpg"

    rekognition = rekognition = boto3.client('rekognition')
    try:
        rekognition_index_response = rekognition.index_faces(CollectionId=collectionId, 
                                    Image={'S3Object': {'Bucket':'rekframebucket','Name':frame_name}},
                                    MaxFaces=1,
                                    QualityFilter="AUTO",
                                    DetectionAttributes=['ALL'])
    except:
        return {
        'statusCode': 500,
        'body': 'Internal Server Error'
    }

    faceId = ''
    for faceRecord in rekognition_index_response['FaceRecords']:
         faceId = faceRecord['Face']['FaceId']
    
    print("This is the face id : ",faceId)
    
    dynamo_client = boto3.resource('dynamodb')
    visitor_table = dynamo_client.Table('visitors')    

    rekognition_bucket = "rekognition-photos"
    photos = []
    photo_dict = {}
    bucket = rekognition_bucket
    createdTimeStamp = int(time.time())
    objKey = name+str(createdTimeStamp)+".jpg"
    photo_dict["objectKey"] = objKey
    photo_dict["bucket"] = bucket
    photo_dict["createdTimeStamp"] = createdTimeStamp
    
    photos.append(photo_dict)

    visitor_table.put_item(
        Item={
                "name": name,
                "faceID" : faceId,
                "phoneNumber" : number,
                "photos" : photos
            } 
    )
    print("Inserted record in visitors table")
    copy_to_photos_bucket(objKey)
    print("Finished inserting photo into bucket")
    otp = generateOTP()
    print("OTP generation is done", otp)
    inserted = insert_into_passcodes(faceId, otp)
    print("Inserted into passcodes table for 5 minutes")
    if inserted :
        send_otp(otp, number)
        print("Message Sent!")
    else:
        print("Message has been recently sent")
    return {
        'statusCode': 200,
        'body': json.dumps('Success')
    }

