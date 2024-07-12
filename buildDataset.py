from __future__ import print_function
import os
import sys
import json
from json.decoder import JSONDecodeError
import requests
from pprint import pprint
import time
from datetime import datetime
import base64

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


# Some parameters for the program
saveArtifacts = True
saveSwarmingTask = False
notification = False
savePassTests = False

resultsFolder = ""
bucket = ""
builderName = ""

def main():
    """
    Main function
    """
    checkUsage()
    startTime = datetime.now()
    

    # Getting arguments
    global resultsFolder
    global bucket
    global builderName

    resultsFolder = sys.argv[1]
    bucket = sys.argv[2]
    builderName = sys.argv[3].replace("%20", " ")
    lastBuildNumber = int(sys.argv[4])
    numberOfBuilds = int(sys.argv[5])

    # Printing information
    print("Bucket " + str(bucket))
    print("Builder " + str(builderName))
    print("Build Number (start) " + str(lastBuildNumber))
    print("Number of builds to analyze " + str(numberOfBuilds))

    # Main Loop
    countBuilds = 0
    for i in range(lastBuildNumber, lastBuildNumber - numberOfBuilds, -1):
        tests = []
        countBuilds += 1
        info = "Build [" + str(countBuilds) + "/" + str(numberOfBuilds) + "]"
        print(info)
        buildNumber = str(i)
        # Get build and test info
        tests.extend(getBuildAndTests(buildNumber))

        # Check if results are already existing
        savedTestsPath = os.path.join(resultsFolder, bucket + "." + sys.argv[3], str(i))
        print(savedTestsPath)
        nbSavedTests = len([ name for name in os.listdir(savedTestsPath) if os.path.isdir(os.path.join(savedTestsPath, name)) ])
        if len(tests) == nbSavedTests:
            print("Tests folders already existing, skipping...")
            continue

        # Get artifacts info
        testsAnalysis(tests, buildNumber, info)


        printTestsInfo(tests)

    sendSms(str(countBuilds) + " builds collected from " + str(builderName))

    # Logging script execution time
    endTime = datetime.now()
    print('Duration: {}'.format(endTime - startTime))

def getBuildAndTests(buildNumber):
    """
    Get Information about a build and its tests, save it to file
    Parameters
    ----------
    buildNumber: The build number
    Returns
    -------
    Return list of all tests (except PASS tests because too many of them)
    """
    testVariants = []

    # Get Build Info
    # Request
    buildInfo = getBuild(buildNumber)

    # Extract build data from response
    # buildNameLong = buildInfo["infra"]["swarming"]["caches"][3]["name"]
    # buildName = buildNameLong.split("_")[1]
    invocation = getInvocation(buildInfo)

    # Get Query Test Variants
    # Request
    testsInfo = queryTestVariants(invocation, "")
    tests = getTests(testsInfo)

    # Add test from initial page to testVariants
    for test in tests:
        if test["status"] != "EXONERATED":
            testVariants.append(test)

    print("Page: 0", len(tests), "tests fetched")

    page = 1
    while "nextPageToken" in testsInfo:
        # Query next page
        testsInfo = queryTestVariants(invocation, testsInfo["nextPageToken"])
        tests = getTests(testsInfo)

        # Track page number
        print("Page:", page, len(tests), "tests fetched.", len(testVariants) + len(tests), "in total.")
        page += 1
        
        # Case when we load all tests except PASS
        if savePassTests == False:
            loadingPass = False
            for test in tests:
                # Add test to test list if it's not a PASS test
                if test["status"] != "EXPECTED" and test["status"] != "EXONERATED":
                    testVariants.append(test)
                else:
                    loadingPass = True
            if loadingPass == True:
                print("No more tests to load")
                break
        # Case when we load all tests including PASS
        else:
            for test in tests:
                if test["status"] != "EXONERATED":
                    testVariants.append(test)

    # Save results to file
    saveBuildAndTestInfo(buildNumber, buildInfo, testVariants)
    return testVariants

# Request to GetBuild
def getBuild(buildNumber):
    """
    GetBuild request
    Parameters
    ----------
    buildNumber
    Returns
    -------
    The response, JSON formatted: Information about the build
    """
    # print("[REQUEST] GetBuild")
    data = '{"builder":{"project":"chromium","bucket":"' + bucket + '","builder":"' + builderName + '"},"buildNumber":' + buildNumber + ',"fields":"*"}'
    for i in range(5):
        try:
            response = requests.post('https://cr-buildbucket.appspot.com/prpc/buildbucket.v2.Builds/GetBuild', headers=headers, data=data)
            if response.status_code != 200:
                print("Error in the response:", response.status_code)
                print("Problem while looking for the build. Check the name of the builder / build number")
                sys.exit(1)
            return reponseToJSON(response)
        except requests.exceptions.RequestException as e:
            print(e)
            time.sleep(2)
            pass
    print("Couldn't load Build")
    sys.exit(1)

  
# Request to QueryTestVariants
def queryTestVariants(invocation, pageToken):
    """
    QueryTestVariants request
    Parameters
    ----------
    invocation: From GetBuild response
    pageToken: From GetBuild response
    Returns
    -------
    The response, JSON formatted: Information about test results
    """
    data = '{"invocations":["' + invocation + '"],"pageToken":"' + pageToken + '"}'
    # print("[REQUEST] QueryTestsVariants")
    # print("[DEBUG] QueryTestVariants data:", data)
    for i in range(5):
        try:
            response = requests.post('https://results.api.cr.dev/prpc/luci.resultdb.v1.ResultDB/QueryTestVariants', headers=headers, data=data)
            if response.status_code != 200:
                print("Error in the response:", response.status_code)
                print("Problem while looking for the tests variants.")
                sys.exit(1)
            return reponseToJSON(response)
        except requests.exceptions.RequestException as e:
            print(e)
            time.sleep(2)
            pass
    print("Couldn't load Tests Variants")
    sys.exit(1)
  
# Request to QueryTestVariants
def querySwarmingTask(taskNumber):
    """
    Swarming Task request
    Parameters
    ----------
    taskNumber: From ?
    Returns
    -------
    The response, JSON formatted: Information about swarming task
    """
    url = "https://chromium-swarm.appspot.com/_ah/api/swarming/v1/task/" + str(taskNumber) + "/result?include_performance_stats=true"

    headers = {
        'authority': 'chromium-swarm.appspot.com',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, \
            like Gecko) Chrome/88.0.4324.192 Safari/537.36',
        'content-type': 'application/json',
        'origin': 'https://ci.chromium.org',
        'sec-fetch-site': 'cross-site',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'authorization': 'Bearer ya29.a0ARrdaM8cS8zhea9Gj6-1QgsSQSm8n3nVimDMsjcIInglNcW8eQ4XpD3kV_bQgYPY-oskYkfdbqeKDtDBIGFuBtSvBjpLe2uxSV-PHe4iXiPdSgR1wAkKj81O7Ux6D3ajONVOofaPicjrFFOosTAvV2R59Rkd0Ug',
        'referer': 'https://ci.chromium.org/',
        'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    for i in range(5):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print("Error in the response:", response.text)
                print("Problem while looking for the swarming task.")
                sys.exit(1)
            return reponseToJSON(response)
        except requests.exceptions.RequestException as e:
            print(e)
            time.sleep(2)
            pass
    print("Couldn't load swarming task")
    sys.exit(1)
  
# Request to ListArtifacts
def listArtifacts(invocation):
    """
    ListArtifacts request
    Parameters
    ----------
    
    Returns
    -------
    The response, JSON formatted: Information about the artifacts
    """
    # print("[REQUEST] ListArtifacts")
    data = '{"parent":"' + invocation + '"}'
    for i in range(5):
        try:
            response = requests.post('https://results.api.cr.dev/prpc/luci.resultdb.v1.ResultDB/ListArtifacts', headers=headers, data=data)
            return reponseToJSON(response)
        except requests.exceptions.RequestException as e:
            print(e)
            time.sleep(2)
            pass
    print("Couldn't load Artifacts")
    sys.exit(1)

# Get tests array from the JSON response
def getTests(testsInfo):
    """
    Get the tests from the response
    Parameters
    ----------
    testInfo: JSON reponse of queryTestVariants

    Returns
    -------
    All test variants as an array
    """
    tests = []
    # Extract tests data from response
    if "testVariants" not in testsInfo:
        print("Apparently no test variants")
        print("JSON Response:", testsInfo) #TODO Check that I don't return [] and add [] to testVariants
    else:
        tests = testsInfo["testVariants"]
    return tests

# Get Invocation from GetBuild response
# Used later for QueryTestVariants
def getInvocation(buildInfo):
    invocation = ""
    # Proto.v2
    if "resultdb" in buildInfo["infra"]["swarming"]:
        invocation = buildInfo["infra"]["swarming"]["resultdb"]["invocation"]
    # Proto.v1
    elif "resultdb" in buildInfo["infra"]:
        invocation = buildInfo["infra"]["resultdb"]["invocation"]
    else:
        print("No invocation found")
    return invocation

def printTestsInfo(testVariants):
    """
    Print details about the retrieved tests
    Parameters
    ----------
    testVariants: From QueryTestVariants response
    Returns
    -------
    Nothing
    """
    countUnexpected = 0
    countSkipped = 0
    countFlaky = 0
    countExonerated = 0
    countExpected = 0
    for test in testVariants:
        if test["status"] == "UNEXPECTED":
            countUnexpected += 1
        if test["status"] == "UNEXPECTEDLY_SKIPPED":
            countSkipped += 1
        if test["status"] == "FLAKY":
            countFlaky += 1
        if test["status"] == "EXONERATED":
            countExonerated += 1
        if test["status"] == "EXPECTED":
            countExpected += 1
    print("\n[TESTS SUMMARY]")
    print("Number of Tests:", len(testVariants))
    print("Number of Unexpected fail tests:", countUnexpected)
    print("Number of Unexpected skipped tests:", countSkipped)
    print("Number of Flaky tests:", countFlaky)
    print("Number of Unexpected pass tests:", countExonerated)
    print("Number of Expected pass tests:", countExpected)

def reponseToJSON(response):
    """
    Convert response to response.json()
    Parameters
    ----------
    response: From requests.post()
    Returns
    -------
    FAIL: -1
    SUCCESS: the jsonResponse
    """
    text = response.text
    try:
        # Strangely, response start with )]}', so we remove the first characters to parse it to JSON
        if text.startswith(")]}'"):
            formattedText = text[5:]
            jsonResponse = json.loads(formattedText)
        else:
            jsonResponse = json.loads(text)
    except JSONDecodeError as error:
        print("Failed:", error)
        print(text)
        print(response)
        return -1
    return jsonResponse

def testsAnalysis(tests, buildNumber, info):
    """
    Once info about tests (queryTestVariants) have been fetched,
    We analyze all tests saved:
    We go through each test, each run, each artifact and save them in ther respective folder
    Parameters
    ----------
    tests: List of tests to consider
    buildNumber: Current build number
    Returns
    -------
    Nothing yet
    """
    if saveSwarmingTask == True:
        swarmingTask = querySwarmingTask("57cbe81f5be23d11")
        print(swarmingTask["task_id"], swarmingTask["performance_stats"]["bot_overhead"])

        
    if saveArtifacts == True:

        print("\n[ANALYSIS]")
        print("Analyzing", len(tests), "tests.")

        builderFolder = bucket + "." + builderName.replace(" ", "%20")
        buildFolder = buildNumber
        buildFolderPath = resultsFolder + "/" + builderFolder + "/" + buildFolder

        # Get build info
        with open(buildFolderPath + "/buildInfo.json") as buildInfoFile:
            buildInfo = json.load(buildInfoFile)
        commitId = buildInfo["input"]["gitilesCommit"]["id"]

        countTest = 0
        for test in tests:
            countTest += 1
            print("\nTest: [", countTest, "/", len(tests), "] ", info, sep="")
            print("Analyzing", len(test["results"]), "test runs.")

            # Create folder for test
            folderNameTest = str(countTest)
            print("Folder name for test:", folderNameTest)
            if not os.path.exists(buildFolderPath + "/" + folderNameTest):
                os.makedirs(buildFolderPath + "/" + folderNameTest)
            # Create file in the folder with testId in it
            testIdFilename = buildFolderPath + "/" + folderNameTest + "/testInfo.json"
            with open(testIdFilename, 'w') as txtFile:
                txtFile.write(json.dumps(test)) 

            # Downloading test source
            print("Downloading test source")
                    
            # Avoid cases where several tests are in the file and where testMetadata is not given
            if "testMetadata" in test and "location" in test["testMetadata"] and "line" not in test["testMetadata"]["location"]:
                repo = test["testMetadata"]["location"]["repo"]
                fileName = test["testMetadata"]["location"]["fileName"][1:]
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
                    filePath = buildFolderPath + "/" + folderNameTest + "/" + fileName.split("/")[-1]
                    with open(filePath, 'w') as txtFile:
                        txtFile.write(message)
                    # print("File saved to", filePath)

            countTestRun = 0
            for testRun in test["results"]:
                countTestRun += 1
                print("- Test run:", countTestRun, "(#" + testRun["result"]["resultId"] +")")

                invocation = testRun["result"]["name"]
                listArtifactsInfo = listArtifacts(invocation)
                if "artifacts" in listArtifactsInfo and len(listArtifactsInfo["artifacts"]) != 0:

                    # Create folder for testRun
                    folderNameTestRun = str(testRun["result"]["resultId"])
                    folderNameTestRunPath = buildFolderPath + "/" + folderNameTest + "/" + folderNameTestRun
                    print("Folder name for testRun:", folderNameTestRun)
                    if not os.path.exists(folderNameTestRunPath):
                        os.makedirs(folderNameTestRunPath)
                    else:
                        # If folder exist, we check artifacts have been downloaded, if yes, we skip
                        if len(os.listdir(folderNameTestRunPath)) == len(listArtifactsInfo["artifacts"]):
                            print("Artifacts already existing, skipping...")
                            continue
                    
                    print("- Analyzing", len(listArtifactsInfo["artifacts"]), "artifacts.")

                    countArtifacts = 0
                    for artifact in listArtifactsInfo["artifacts"]:
                        countArtifacts += 1
                        print("--- Artifact:", countArtifacts)
                        if "fetchUrl" not in artifact or "artifactId" not in artifact or "contentType" not in artifact:
                            continue
                        artifactURL = artifact["fetchUrl"]
                        artifactType = artifact["artifactId"]
                        artifactContentType = artifact["contentType"]

                        # Create file with artifact in it
                        artifactBaseFilename = folderNameTestRunPath + "/" + str(artifactType)
                        # Request txt artifact
                        if artifactContentType == "text/plain":
                            for i in range(5):
                                try:
                                    artifactRequest = requests.get(artifactURL, headers=headers)
                                    if artifactRequest.status_code == 200:
                                        with open(artifactBaseFilename + ".txt", 'w') as txtFile:
                                            try:
                                                txtFile.write(artifactRequest.text)
                                            except UnicodeEncodeError:
                                                os.remove(artifactBaseFilename + ".txt")
                                                break
                                    break
                                except requests.exceptions.RequestException as e:
                                    print(e)
                                    time.sleep(2)
                                    pass
                        # Request html artifact
                        if artifactContentType == "text/html":
                            for i in range(5):
                                try:
                                    artifactRequest = requests.get(artifactURL, headers=headers)
                                    if artifactRequest.status_code == 200:
                                        with open(artifactBaseFilename + ".html", 'w') as txtFile:
                                            try:
                                                txtFile.write(artifactRequest.text)
                                            except UnicodeEncodeError:
                                                os.remove(artifactBaseFilename + ".html")
                                                break
                                    break
                                except requests.exceptions.RequestException as e:
                                    print(e)
                                    time.sleep(2)
                                    pass

def saveBuildAndTestInfo(buildNumber, buildInfo, tests):
    builderFolder = bucket + "." + builderName.replace(" ", "%20")
    buildFolder = buildNumber
    buildFolderPath = resultsFolder + "/" + builderFolder + "/" + buildFolder
    fileNameBuildInfo = "buildInfo"
    fileNameTestsInfo = "testsInfo"

    if not os.path.exists(resultsFolder):
        os.makedirs(resultsFolder)
    if not os.path.exists(resultsFolder + "/" + builderFolder):
        os.makedirs(resultsFolder + "/" + builderFolder)
    if not os.path.exists(buildFolderPath):
        os.makedirs(buildFolderPath)

    print("\n[SAVING FILES]")
    saveResults(buildInfo, buildFolderPath, fileNameBuildInfo)
    saveResults(tests, buildFolderPath, fileNameTestsInfo)

def saveResults(dataset, folder, name):
    filename = folder + "/" + name + ".json"
    with open(filename, 'w') as jsonFile:
        json.dump(dataset, jsonFile)
    print("File saved to ", filename)

def error_print(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def sendSms(msg):
    """Sends a message."""

    if notification == False:
        return

    if not os.path.exists("./credentials.json"):
        print("No credential found for SMS notification.")
        return

    with open('./credentials.json') as data_file:
        data = json.load(data_file)

    user = data['username']
    pwd =  data['password']

    response = requests.post("https://smsapi.free-mobile.fr/sendmsg",
        json={
            "user": user,
            "pass": pwd,
            "msg": msg
        })

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
    #Check the programs' arguments
    if len(sys.argv) != 6 or not os.path.isdir(sys.argv[1]):
        print("Usage:")
        print("- To get info of a BUILDER_NAME starting with build # BUILD_NUMBER and then NB_BUILDS before it.")
        print("python main.py BUCKET BUILDER_NAME BUILD_NUMBER NB_BUILDS")
        sys.exit(1)

if __name__ == "__main__":
    main()
