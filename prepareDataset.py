import os
import sys
import pandas as pd
import json
from pprint import pprint
from datetime import datetime
import time
from tqdm import tqdm

def main():
    """
    Main function
    """
    checkUsage()
    startTime = datetime.now()
    
    print("--- Chromium Analysis | Prepare Dataset ---\n")

    resultsPath = sys.argv[1]
    datasetName = sys.argv[1].split(".")[-1]

    dataset = []
    runTagStatusList = []
    testSuites = []

    countSkippedDataPoint = 0
    countUnicodeEncodeError = 0
    countBuildDir = 0

    heartBeatWindowSize = 40
    heartBeat = {}
    heartBeatFlaky = {}

    for buildDir in tqdm(sorted(os.scandir(resultsPath), key=lambda e: e.name)):
        if os.path.isdir(buildDir):
            countBuildDir += 1
            heartBeat[buildDir.name] = []
            heartBeatFlaky[buildDir.name] = []
            with open(buildDir.path + "/testsInfo.json") as testsInfo:
                data = json.load(testsInfo)
                countTest = 0
                for test in data:
                    countTest += 1
                # TEST NAME
                    # Test ID
                    if "testId" not in test:
                        countSkippedDataPoint += 1
                        continue
                    # Test Suite
                    if "variant" not in test:
                        countSkippedDataPoint += 1
                        continue
                    if "def" not in test["variant"]:
                        countSkippedDataPoint += 1
                        continue
                    if "test_suite" not in test["variant"]["def"]:
                        countSkippedDataPoint += 1
                        continue
                    testSuite = test["variant"]["def"]["test_suite"]
                    testId = testSuite + "_" + test["testId"]
                # TEST SUITE
                    if testSuite not in testSuites:
                        testSuites.append(testSuite)
                    testSuiteNumber = testSuites.index(testSuite)
                # TEST STATUS
                    if "status" not in test:
                        countSkippedDataPoint += 1
                        continue
                    else:
                        testStatus = test["status"]
                        if test["status"] == "FLAKY":
                            # testStatus = 0
                            # History of flaky
                            heartBeatFlaky[buildDir.name].append(testId)
                        elif test["status"] == "UNEXPECTED":
                            # testStatus = 3
                            # History of failure
                            heartBeat[buildDir.name].append(testId)
                
                # TEST SOURCE
                    testSourceContent = ""
                    for file in os.scandir(os.path.join(buildDir.path, str(countTest))):
                        if not file.is_dir() and "testInfo.json" not in file.name:
                            with open(file.path) as testSource:
                                try:
                                    testSourceContent = testSource.read()
                                except UnicodeDecodeError:
                                    testSourceContent = ""
                                    countUnicodeEncodeError += 1

                # RUNS
                    for run in test["results"]:
                        # Run status
                        if "status" not in run["result"]:
                            countSkippedDataPoint += 1
                            continue
                        else:
                            runStatus = run["result"]["status"]
                        # if run["result"]["status"] == "ABORT":
                        #     runStatus = 0
                        # elif run["result"]["status"] == "FAIL":
                        #     runStatus = 1
                        # elif run["result"]["status"] == "PASS":
                        #     runStatus = 2
                        # elif run["result"]["status"] == "CRASH":
                        #     runStatus = 3
                        # elif run["result"]["status"] == "SKIP":
                        #     runStatus = 4
                        # else:
                        #     pprint(run)
                        #     print("Unhandle Run Status", run["result"]["status"])
                        #     sys.exit(1)

                        # Run duration
                        if "duration" not in run["result"]:
                            runDuration = 0
                        else:
                            runDuration = float(run["result"]["duration"][:-1])
                        # Run tag status
                        if "tags" not in run["result"]:
                            countSkippedDataPoint += 1
                            continue
                        hasTag = False
                        for tag in run["result"]["tags"]:
                            if tag["key"] in ["web_tests_result_type", "gtest_status", "typ_expectation"]:
                                runTagStatus = tag["value"]
                                hasTag = True
                                if runTagStatus not in runTagStatusList:
                                    runTagStatusList.append(runTagStatus)
                        if not hasTag:
                            countSkippedDataPoint += 1
                            continue
                        # if runTagStatus == "CRASH":
                        #     runTagStatus = 0
                        # elif runTagStatus == "PASS":
                        #     runTagStatus = 1
                        # elif runTagStatus == "FAIL":
                        #     runTagStatus = 2
                        # elif runTagStatus == "TIMEOUT":
                        #     runTagStatus = 3
                        # elif runTagStatus == "SUCCESS":
                        #     runTagStatus = 4
                        # elif runTagStatus == "FAILURE":
                        #     runTagStatus = 5
                        # elif runTagStatus == "FAILURE_ON_EXIT":
                        #     runTagStatus = 6
                        # elif runTagStatus == "NOTRUN":
                        #     runTagStatus = 7
                        # elif runTagStatus == "SKIP":
                        #     runTagStatus = 8
                        # elif runTagStatus == "UNKNOWN":
                        #     runTagStatus = 9
                        # else:
                        #     pprint(run)
                        #     print("Unhandle Run Tag Status", runTagStatus)
                        #     sys.exit(1)
                        # Flaky
                        if testStatus == "FLAKY" and runStatus != "PASS":
                            label = 0
                        # Failure
                        elif testStatus == "UNEXPECTED" and runTagStatus != "PASS":
                            label = 1
                        elif testStatus == "EXPECTED" and runTagStatus == "PASS":
                            label = 2
                        # AVOID UNINTERESTING TEST
                        else:
                            continue

                        # Artifacts
                        artifactDir = os.path.join(buildDir.path, str(countTest), run["result"]["resultId"])
                        stackTrace = ""
                        command = ""
                        stderr = ""
                        crashlog = ""
                        if os.path.isdir(artifactDir):
                            for artifact in os.scandir(artifactDir):
                                if artifact.name == "stack_trace.txt":
                                    with open(artifact.path) as artifactFile:
                                        stackTrace = artifactFile.read()
                                if artifact.name == "command.txt":
                                    with open(artifact.path) as artifactFile:
                                        command = artifactFile.read()
                                if artifact.name == "stderr.txt":
                                    with open(artifact.path) as artifactFile:
                                        stderr = artifactFile.read()
                                if artifact.name == "crash_log.txt":
                                    with open(artifact.path) as artifactFile:
                                        crashlog = artifactFile.read()
                        
                        # Add dataPoint
                        buildId = int(buildDir.name)
                        # Avoid odd builds Linux
                        # if buildId >= 98177 and buildId <= 98192:
                        # Avoid odd builds LinuxRecent
                        if buildId >= 122993 and buildId <= 123002 or buildId >= 122725 and buildId <= 122739 or buildId == 117063:
                            continue
                        # Avoid odd builds Mac
                        if buildId >= 8554 and buildId <= 8567:
                            continue
                        # Avoid odd builds Windows
                        if buildId >= 53760 and buildId <= 53768:
                            continue
                        
                        dataPoint = {
                            "testId": testId,
                            "buildId": buildId,
                            "testStatus": testStatus,
                            # "testSuiteNumber": testSuiteNumber,
                            "testSuite": testSuite,
                            "runStatus": runStatus,
                            "runDuration": runDuration,
                            "runTagStatus": runTagStatus,
                            "stackTrace": stackTrace,
                            "command": command,
                            "stderr": stderr,
                            "crashlog": crashlog,
                            "testSource": testSourceContent,
                            "stackTraceLength": len(stackTrace),
                            "commandLength": len(command),
                            "stderrLength": len(stderr),
                            "crashlogLength": len(crashlog),
                            "testSourceLength": len(testSourceContent),
                            "label": label
                        }
                        dataset.append(dataPoint)
    
    # saveDataset(dataset, "./dataset.mfr.Linux.json")

    print("Skipped data points due to missing values:", countSkippedDataPoint)
    print("Number of UnicodeEncodeError:", countUnicodeEncodeError)
    print("Total number of data points:", len(dataset))
    print("Computing flaky and failure rates...")

    # HEART BEAT INFORMATION
    pastOnly = True

    finalDataset = []
    for element in dataset:
        buildId = element["buildId"]
        testId = element["testId"]
        # HEART BEAT
        # Computed after the window is enough (beginning and end)
        if pastOnly == True:
            buildsToConsiderLinux = int(buildId) >= 113039 + heartBeatWindowSize + 1    #97983 + heartBeatWindowSize + 1
            buildsToConsiderMac = int(buildId) >= 8382 + heartBeatWindowSize + 1
            buildsToConsiderWindows = int(buildId) >= 53336 + heartBeatWindowSize + 1
        else:
            buildsToConsiderLinux = int(buildId) >= 97983 + heartBeatWindowSize + 1 and int(buildId) < 98982 - heartBeatWindowSize
            buildsToConsiderMac = int(buildId) >= 8382 + heartBeatWindowSize + 1 and int(buildId) < 9381 - heartBeatWindowSize
            buildsToConsiderWindows = int(buildId) >= 53336 + heartBeatWindowSize + 1 and int(buildId) < 54335 - heartBeatWindowSize
        
        if buildsToConsiderLinux and datasetName == "Linux" or buildsToConsiderLinux and datasetName == "LinuxRecent" or buildsToConsiderLinux and datasetName == "sampleLinux" or buildsToConsiderMac and datasetName == "Mac"  or buildsToConsiderWindows and datasetName == "Windows":
            statusList = []
            statusListFlaky = []

            # Browsing history 
            if pastOnly == True:
                limit = int(buildId)
            else:
                limit = int(buildId) + heartBeatWindowSize

            for i in range(int(buildId) - heartBeatWindowSize, limit):
                # Avoid considering current build
                if i == int(buildId):
                    continue
                # Computing heartbeats for flake and failure rates
                build = heartBeat[str(i)]
                buildFlaky = heartBeatFlaky[str(i)]
                if testId in build:
                    statusList.append(True)
                else:
                    statusList.append(False)
                if testId in buildFlaky:
                    statusListFlaky.append(True)
                else:
                    statusListFlaky.append(False)
            # Computing rates and adding to element
            element["flakeRate"] = flakeRate(statusListFlaky)
            element["failureRate"] = flakeRate(statusList)
            element["failureFlipRate"] = flipRate(statusList)
            element["flakyFlipRate"] = flipRate(statusListFlaky)
            # Adding to final dataset
            finalDataset.append(element)
    
    saveDataset(finalDataset, "./dataset." + str(heartBeatWindowSize) + "past." + datasetName + ".json")

    # Save test suites ids
    # testSuitesDic = {}
    # for testSuite in testSuites:
    #     testSuitesDic[testSuites.index(testSuite)] = testSuite
    # saveDataset(testSuitesDic, "./testSuites." + datasetName + ".json")
    

    # Logging script execution time
    endTime = datetime.now()
    print('Duration: {}'.format(endTime - startTime))

def flakeRate(statusList):
    c = 0
    for i in range(len(statusList)):
        if statusList[i] == True:
            c += 1
    return c / len(statusList)


def flipRate(statusList):
    c = 0
    for i in range(len(statusList)-1):
        if statusList[i] != statusList[i+1]:
            c += 1
    return c / (len(statusList) - 1)

def saveDataset(dataset, fileName):
    with open(fileName, 'w') as jsonFile:
        json.dump(dataset, jsonFile, sort_keys=True, indent=4)
    print("File saved to ", fileName)
    

def checkUsage():
    """
    Check Usage
    """
    #Check the programs' arguments
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        print("Usage:")
        print("python prepareDataset.py /path/to/results/folder")

if __name__ == "__main__":
    main()
