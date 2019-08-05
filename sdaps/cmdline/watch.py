# -*- coding: utf-8 -*-
# SDAPS - Scripts for data acquisition with paper based surveys
# Copyright(C) 2008, Christoph Simon <post@christoph-simon.eu>
# Copyright(C) 2010, Benjamin Berg <benjamin@sipsolutions.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#from sdaps import model
import os
from sdaps import script
from sdaps import defs
from sdaps import recognize
from sdaps import model
from sdaps import image
from path import Path
import os, subprocess, tempfile, shutil
from pyzbar  import pyzbar
import argparse
import cv2
import datetime
import csv

from sdaps.utils.ugettext import ugettext, ungettext
_ = ugettext

def barcodeDetect(image):

    # load the input image
    imageload = cv2.imread(image)

    # find the barcodes in the image and decode each of the barcodes
    barcodes = pyzbar.decode(imageLoad)

    facturation = 'None'
    project = 'None'
    # loop over the detected barcodes
    for barcode in barcodes:
        barcodedata = barcode.data.decode("utf-8")
        if len(barcodedata) == 9:
            facturation = barcodedata
            print(facturation)
        elif len(barcodedata) == 14:
            project = barcodedata[0:-4]
            print(project)
    print(project , facturation)
    return (project , facturation)

parser = script.add_project_subparser("watch",
    help=_("Watching for new scan commit"),
    description=_("""Watch in a specified folder to detect a new scan,
    convert and push it to the right project."""))

parser.add_argument('--scanFolder','-sf',
    help=_("Folder to be watched"))

# parser.add_argument('--projectsFolder','-pf',
#     help=_("Folder containing SDAPS projects"))

# parser.add_argument('--processedFolder','-pcdf',
#     help=_("Folder with already processed scans"))

@script.connect(parser)
def watch(cmdline):

    # We need a survey that has the correct definitions (paper size, duplex mode)
    # Assume the first argument is a survey
    if os.path.exists('./WATCH/info'):
        pass
    else :
        subprocess.call(['sdaps', 'setup', 'WATCH', './watch.tex'])

    survey = model.survey.Survey.load('WATCH')

    # We need the recognize buddies, as they are able to identify the data
    from sdaps.recognize import buddies

    # A sheet object to attach the images to
    sheet = model.sheet.Sheet()
    survey.add_sheet(sheet)

    images = []
    scans = os.listdir(cmdline['scanFolder'])
    print('Files found :'+str(scans))

    for file in scans:
        num_pages = image.get_tiff_page_count(cmdline['scanFolder']+"/"+file)
        for page in range(num_pages):
            images.append((cmdline['scanFolder']+"/"+file, page))

    if len(images) == 0:
        # No images, simply exit again.
        sys.exit(1)


    def add_image(survey, tiff, page):
        img = model.sheet.Image()
        survey.sheet.add_image(img)
        # SDAPS assumes a relative path from the survey directory
        img.filename = os.path.relpath(os.path.abspath(tiff), survey.survey_dir)
        img.orig_name = tiff
        img.tiff_page = page
        print('Images added :'+str(img.filename)+str(img.orig_name)+str(img.tiff_page))

    while images:
        # Simply drop the list of images again.
        sheet.images = []

        add_image(survey, *images.pop(0))

        if survey.defs.duplex:
            add_image(survey, *images.pop(0))

        sheet.recognize.recognize()

        for img in sheet.images:
            print(img.orig_name, img.tiff_page)
            print('\tPage:', img.page_number)
            print('\tRotated:', img.rotated)
            print('\tMatrix (px to mm):', img.raw_matrix)
            print('\tSurvey-ID:', sheet.survey_id)
            print('\tGlobal-ID:', sheet.global_id)
            print('\tQuestionnaire-ID:', sheet.questionnaire_id)
            print()

# And, we simply quit, ie. we don't save the survey
#     #creating project dictionnary
#     surveyIdList = {}
#
#     #list of all subfolders containing 'info'
#     for file in Path(cmdline['projectsFolder']).walkfiles('info'):
#         s = file.dirname()
#         with open(s+'/info', "r") as infoFile:
#     #looking for survey id and add it to the dictionnary
#             lines = infoFile.read()
#             line = lines.split('\n')
#             for l in line :
#                 words = l.split(' = ')
#                 if words[0] == 'survey_id':
#                     print('DETECT ! : '+words[1])
#                     surveyIdList[words[1]] = s
#     with open('surveyList.csv', 'w') as f:
#         for key in surveyIdList.keys():
#             f.write("%s,%s\n"%(key,surveyIdList[key]))
#
#     #file retrieval
#     scans = os.listdir(cmdline['scanFolder'])
#
#     #temp folder creation
#     tempd = tempfile.mkdtemp()
#
#     #folder with alreay processed scans
#
#     processedd = cmdline['processedFolder']
#     #convert and copy
#     for scan in scans:
#         scan_title, scan_extension = os.path.splitext(scan)
#         if scan_extension != '.tif' or scan_extension != '.tiff' and scan_extension == '.pdf':
#             print('File', scan, 'found, trying to convert')
#             subprocess.call(['pdfimages', '-tiff', cmdline['scanFolder']+'/'+scan, tempd+'/'+scan_title])
#         elif scan_extension == '.tif' or scan_extension == '.tiff':
#             subprocess.call(['cp', cmdline['scanFolder']+'/'+scan, tempd+'/'+scan])
#         else:
#             print('Wrong image format for file'+scan)
#
#     images = os.listdir(tempd)
#
#     processedList = []
#     for image in images:
#         surveyid = barcodeDetect(tempd + '/' + image)[0]
#         facturation = barcodeDetect(tempd + '/' + image)[1]
#         print(surveyid)
#         if surveyid in surveyIdList:
#             projectname = surveyIdList[surveyid]
#             print (image+' found with '+surveyid+' ID, adding do the '+projectname)
#             subprocess.call(['cp', tempd+'/'+scan, processedd+'/'+surveyid+".tif"])
#             subprocess.call(['sdaps', 'add', projectname, tempd+'/'+image, '--convert'])
#             subprocess.call(['sdaps', 'recognize', projectname])
#             subprocess.call(['sdaps', 'csv', 'export', projectname])
#             newrow = [facturation , surveyid , datetime.datetime.now() ]
#             processedList.append(newrow)
#
#     with open('processedList.csv', 'w', newline='') as f:
#         wr = csv.writer(f, quoting=csv.QUOTE_ALL)
#         wr.writerow(processedList)
#
#     #cleaning
#     for scan in scans:
#         os.remove(cmdline['scanFolder']+'/'+scan)
#     shutil.rmtree(tempd)
