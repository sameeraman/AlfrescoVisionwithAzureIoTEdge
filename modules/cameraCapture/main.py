# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for
# full license information.

import time
import sys
import os
import requests
import json
import shutil
from azure.iot.device import IoTHubModuleClient, Message
import paho.mqtt.client as mqtt

# global counters
SENT_IMAGES = 0

# global client
CLIENT = None

# Send a message to IoT Hub
# Route output1 to $upstream in deployment.template.json
def send_to_hub(strMessage):
    message = Message(bytearray(strMessage, 'utf8'))
    CLIENT.send_message_to_output(message, "output1")
    global SENT_IMAGES
    SENT_IMAGES += 1
    print( "Total images sent: {}".format(SENT_IMAGES) )


# Find Probability in the JSON values. 
def findprobablity (attributeName,jsonObject):
    for entry in jsonObject["predictions"]:
        if attributeName == entry ['tagName']:
            return entry ['probability']
        else:
            return 0

# Send an image to the image classifying server
# Return the JSON response from the server with the prediction result
def sendFrameForProcessing(imagePath, imageProcessingEndpoint):



    # Process Image
    headers = {'Content-Type': 'application/octet-stream'}

    with open(imagePath, mode="rb") as test_image:
        try:
            response = requests.post(imageProcessingEndpoint, headers = headers, data = test_image)
            print("Response from classification service: (" + str(response.status_code) + ") " + json.dumps(response.json()) + "\n")
        except Exception as e:
            print(e)
            print("Response from classification service: (" + str(response.status_code))

    return json.dumps(response.json())

def main(imagePath, imageProcessingEndpoint):
    try:
        print ( "Simulated camera module for Azure IoT Edge. Press Ctrl-C to exit." )

        try:
            global CLIENT
            CLIENT = IoTHubModuleClient.create_from_edge_environment()
        except Exception as iothub_error:
            print ( "Unexpected error {} from IoTHub".format(iothub_error) )
            return

        print ( "The sample is now sending images for processing and will indefinitely.")

        while True:
            # Get image from HomeAssistant
            url = CAMERA_CAPTURE_URL
            response = requests.get(url, stream=True)
            with open(imagePath, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
            del response

            # Process Image
            classification = sendFrameForProcessing(imagePath, imageProcessingEndpoint)

            # find Active Probablity 
            probability = findprobablity("active", json.loads(classification))

            # update MQTT sensor
            client = mqtt.Client()
            client.username_pw_set(MQTTUSER, MQTTPASSWORD)
            client.connect(MQTTBROKER,1883,60)
            if float(probability) > float(PROBABILITY_THRESHOLD):
                client.publish("home/alfresco/image_processing_sensor/state", "on")
            else:
                client.publish("home/alfresco/image_processing_sensor/state", "off")
            client.disconnect()

            # send to IoT Hub
            send_to_hub(classification)
            time.sleep(15)

    except KeyboardInterrupt:
        print ( "IoT Edge module sample stopped" )

if __name__ == '__main__':
    try:
        # Retrieve the image location and image classifying server endpoint from container environment
        IMAGE_PATH = os.getenv('IMAGE_PATH', "")
        IMAGE_PROCESSING_ENDPOINT = os.getenv('IMAGE_PROCESSING_ENDPOINT', "")
        PROBABILITY_THRESHOLD = os.getenv('PROBABILITY_THRESHOLD', "")
        CAMERA_CAPTURE_URL = os.getenv('CAMERA_CAPTURE_URL', "")
        MQTTBROKER = os.getenv('MQTTBROKER', "")
        MQTTUSER = os.getenv('MQTTUSER', "")
        MQTTPASSWORD = os.getenv('MQTTPASSWORD', "")

    except ValueError as error:
        print ( error )
        sys.exit(1)

    if ((IMAGE_PATH and IMAGE_PROCESSING_ENDPOINT) != ""):
        main(IMAGE_PATH, IMAGE_PROCESSING_ENDPOINT)
    else: 
        print ( "Error: Image path or image-processing endpoint missing" )