import os
import sys
import json
from pprint import pprint
import matplotlib.pyplot as plt
from tqdm import tqdm
import requests
import base64
import time

# Header for the request
headers = {
    'authority': 'results.api.cr.dev',
    'accept': 'application/json',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, \
        like Gecko) Chrome/88.0.4324.192 Safari/537.36',
    'content-type': 'application/json',
    'origin': 'https://ci.chromium.org',
    'sec-fetch-site': 'cross-site',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
    'referer': 'https://ci.chromium.org/',
    'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
}

def main():
    """
    Main function
    """
    checkUsage()
    
    resultsPath = sys.argv[1]
    count = {}

    # For all build folders
    for buildDir in tqdm(sorted(os.scandir(resultsPath), key=lambda e: e.name)):
        count[buildDir.name] = 0
        if os.path.isdir(buildDir):
            # Get build info
            with open(buildDir.path + "/buildInfo.json") as buildInfoFile:
                buildInfo = json.load(buildInfoFile)
            commitId = buildInfo["input"]["gitilesCommit"]["id"]
            
            # For all test folders
            for testDir in tqdm(sorted(os.scandir(buildDir.path), key=lambda e: e.name)):
                if os.path.isdir(testDir):
                    # print(testDir.name)
                    # Get test info
                    with open(testDir.path + "/testInfo.json") as testInfoFile:
                        testinfo = json.load(testInfoFile)
                    # Don't get EXONERATED tests
                    if testinfo["status"] != "EXONERATED":
                        
                        # Avoid cases where several tests are in the file and where testMetadata is not given
                        if "testMetadata" in testinfo and "location" in testinfo["testMetadata"] and "line" not in testinfo["testMetadata"]["location"]:
                            repo = testinfo["testMetadata"]["location"]["repo"]
                            fileName = testinfo["testMetadata"]["location"]["fileName"][1:]
                            url = repo + "/+/" + commitId + fileName + "?format=TEXT"
                            # print(repo)
                            # print(commitId)
                            # print(fileName)
                            # print(url)
                            source = getSource(url)
                            base64_message = source
                            base64_bytes = base64_message.encode('utf-8')
                            message_bytes = base64.b64decode(base64_bytes)
                            try:
                                message = message_bytes.decode('utf-8')
                            except UnicodeDecodeError:
                                message = ""
                            #print(message) 
                            if message != "":
                                filePath = testDir.path + "/" + fileName.split("/")[-1]
                                count[buildDir.name] += 1
                                with open(filePath, 'w') as txtFile:
                                    txtFile.write(message)
                                # print("File saved to", filePath)
        with open("./getSource-logs.txt", 'w') as txtFile:
            txtFile.write(json.dumps(count))
        
                

def getSource(url):
    source = ""
    for i in range(5):
        response = requests.get(url, headers=headers)
        if response.status_code == 429:
            wait = 2 * (i + 1)
            time.sleep(wait)
            continue
        if response.status_code != 200:
            print("Error in the response:", response.status_code)
            print(url)
            print("Problem while looking for the source.")
            break
        source = response.text
        return source
    print("Couldn't load source after 5 waits")
    return source
    
def checkUsage():
    """
    Check Usage
    """
    print("--- Chromium Analysis | Info Dataset ---")
    #Check the programs' arguments
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        print("Usage:")
        print("python getSource.py /path/to/folder/results/builder/")
        sys.exit(1)

if __name__ == "__main__":
    main()