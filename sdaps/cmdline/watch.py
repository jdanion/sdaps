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
import os, subprocess, tempfile, shutil
from sdaps import convert
from sdaps import script
#from sdaps import defs
from sdaps import recognize
from sdaps import model
from sdaps import image
from sdaps.utils import opencv
#from sdaps.recognize import buddies
from path import Path

#from pyzbar  import pyzbar
import argparse
#import cv2
import datetime
import csv

from sdaps.utils.ugettext import ugettext, ungettext
_ = ugettext

# def barcodeDetect(image):
#
#     # load the input image
#     imageload = cv2.imread(image)
#
#     # find the barcodes in the image and decode each of the barcodes
#     barcodes = pyzbar.decode(imageLoad)
#
#     facturation = 'None'
#     project = 'None'
#     # loop over the detected barcodes
#     for barcode in barcodes:
#         barcodedata = barcode.data.decode("utf-8")
#         if len(barcodedata) == 9:
#             facturation = barcodedata
#             print(facturation)
#         elif len(barcodedata) == 14:
#             project = barcodedata[0:-4]
#             print(project)
#     print(project , facturation)
#     return (project , facturation)

parser = script.add_project_subparser("watch",
    help=_("Watching for new scan commit"),
    description=_("""Watch in a specified folder to detect a new scan,
    convert and push it to the right project."""))

parser.add_argument('--scanFolder', '-sf',
    help=_("Folder to be watched"))

parser.add_argument('--projectsFolder', '-pf',
    help=_("Folder containing SDAPS projects"))

parser.add_argument('--renamedFolder','-rf',
    help=_("Folder with renamed and processed scans"))

@script.connect(parser)
def watch(cmdline):

    # We need a survey that has the correct definitions (paper size, duplex mode)
    # Assume the first argument is a survey
    if os.path.exists('./WATCH/info'):
        print('WATCH project found, processing')
        pass
    else :
        print('Creating new WATCH project')
        subprocess.call(['sdaps', 'setup', 'WATCH', './watch.tex'])
    watchtexpath = (os.path.dirname(os.path.abspath(__file__)))
    #loading dummy survey
    print('Loading WATCH project')
    survey = model.survey.Survey.load('WATCH')

    # A sheet object to attach the images to
    sheet = model.sheet.Sheet()
    survey.add_sheet(sheet)

    print('Listing all projects in ProjectsFolder')

    #creating project dictionnary
    surveyIdList = {}

    #list of all subfolders containing 'info'
    for file in Path(cmdline['projectsFolder']).walkfiles('info'):
        s = file.dirname()
        with open(s+'/info', "r") as infoFile:
    #looking for survey id and add it to the dictionnary
            lines = infoFile.read()
            line = lines.split('\n')
            for l in line :
                words = l.split(' = ')
                if words[0] == 'survey_id':
                    print('DETECT ! : '+words[1])
                    surveyIdList[words[1]] = s
    with open('surveyList.csv', 'w') as f:
        for key in surveyIdList.keys():
            f.write("%s,%s\n"%(key,surveyIdList[key]))

    #file retrieval
    print('Listing scanned files')
    scans = os.listdir(cmdline['scanFolder'])

    print(scans)

    #temp folder creation
    tempd = tempfile.mkdtemp()
    print('Temp folder :'+tempd)

    #folder with alreay processed scans
    renamedFolder = cmdline['renamedFolder']

    def is_tiff(scanned):
        scan_title, scan_extension = os.path.splitext(scanned)
        if scan_extension == '.tif' or scan_extension == '.tiff':
            return True
        else:
            return False

    def is_pdf(scanned):
        scan_title, scan_extension = os.path.splitext(scanned)
        if scan_extension == '.pdf':
            return True
        else:
            return False


   #convert and copy
    for scan in scans:
        scan_title, scan_extension = os.path.splitext(scan)
        print(scan_title, scan_extension)
        if is_pdf(scan):
            print('PDF file found')
            print('Scan title '+scan_title, 'Scan extension '+scan_extension)
            tempscanpdf = tempfile.mktemp(suffix='.pdf',dir=tempd)
            tempscantif = tempfile.mktemp(suffix='.tif',dir=tempd)
            print('File', str(cmdline['scanFolder']+'/'+scan), 'found, trying to convert to '+tempscantif)
            subprocess.call(['cp', cmdline['scanFolder']+'/'+scan, tempscanpdf])
            print('Copied'+str(cmdline['scanFolder']+'/'+scan)+'to '+tempscanpdf)
            #subprocess.call(['sdaps', 'add', "WATCH", tempscanpdf, '--convert'])
            # for i, (img, filename, page) in enumerate(opencv.iter_images_and_pages(tempscanpdf)):
            #     print(img)
            #     print(filename)
            #     print(page)
            scantoconvert = []
            scantoconvert.append(tempscanpdf)
            convert.convert_images(scantoconvert, tempscantif, survey.defs.paper_width, survey.defs.paper_height)
            #subprocess.call(['pdfimages', '-tiff', cmdline['scanFolder']+'/'+scan, tempd+'/'+scan_title])
        elif is_tiff(scan):
            print('TIFF file found')
            tempscantif = tempfile.mktemp(suffix='.tif',dir=tempd)
            subprocess.call(['cp', cmdline['scanFolder']+'/'+scan, tempscantif])
        else:
             print('Wrong image format for file '+scan+', ignoring')

    #we retrieve all tiff to be processed
    tiffscans = filter(is_tiff, os.listdir(tempd))

    images = []

    print('File list to be processed : '+str(tiffscans))

    for file in tiffscans:
        num_pages = image.get_tiff_page_count(tempd+'/'+file)
        print(num_pages)
        for page in range(num_pages):
            images.append((tempd+"/"+file, page))


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
        #print('Images added :'+str(img.filename)+str(img.orig_name)+str(img.tiff_page))
        imgdummy = model.sheet.Image()
        survey.sheet.add_image(imgdummy)
        imgdummy.orig_name = "DUMMY"
        imgdummy.filename = "DUMMY"
        imgdummy.tiff_page = -1
        imgdummy.ignored = True
        #print('Images added :'+str(imgdummy.filename)+str(img.orig_name)+str(imgdummy.tiff_page))

    while images:
        # Simply drop the list of images again.
        sheet.images = []

        add_image(survey, *images.pop(0))
        print('Adding image simplex mode')

        if survey.defs.duplex:
            print('Adding image duplex mode')
            add_image(survey, *images.pop(0))

        #print(images)

        print ('RECOGNIZE ')

        sheet.recognize.recognize()
    #
        for img in sheet.images:
            dictID = {}
            if img.tiff_page != -1:
                print(img.orig_name, img.tiff_page)
                print('\tPage:', img.page_number)
                print('\tRotated:', img.rotated)
                print('\tMatrix (px to mm):', img.raw_matrix)
                print('\tSurvey-ID:', sheet.survey_id)
                tmpdictID = {'QID':sheet.questionnaire_id, 'SID':sheet.survey_id, 'BID':sheet.barcode_id, 'GID':sheet.global_id}
                tempSID = sheet.survey_id
                print('\tGlobal-ID:', sheet.global_id)
                tempGID = sheet.global_id
                print('\tBarcode-ID:', sheet.barcode_id)
                tempBID = sheet.barcode_id
                print('\tQuestionnaire-ID:', sheet.questionnaire_id)
                tempQID = sheet.questionnaire_id
                now = datetime.datetime.now()
                datestamp = now.strftime('%Y%m%d%H%M%S%f')
                tiffname = str(renamedFolder)+'DATE'+str(datestamp)+'QID'+str(sheet.questionnaire_id)+'SRVID'+str(sheet.survey_id)+'BID'+str(sheet.barcode_id)
            
            subprocess.call(['cp', img.orig_name, tiffname+".tif"])
            #img.save(sheet.survey_id+'.tif')
    # processedList = []
    #
    # for tiffScan in tiffScans:
    #     # A sheet object to attach the images to
    #     sheet = model.sheet.Sheet()
    #     survey.add_sheet(sheet)
    #
    #     print('Files found :'+str(tiffScans))
    #     tmptiff = []
    #     for tiff in tiffs:
    #         num_pages = image.get_tiff_page_count(cmdline['scanFolder']+"/"+tiff)
    #         for page in range(num_pages):
    #             tpmtiff.append((cmdline['scanFolder']+"/"+tiff, page))
    #
    #     if len(tpmtiffs) == 0:
    #         # No images, simply exit again.
    #         sys.exit(1)
    #
    #     def add_image(survey, tiff, page):
    #         img = model.sheet.Image()
    #         survey.sheet.add_image(img)
    #         # SDAPS assumes a relative path from the survey directory
    #         img.filename = os.path.relpath(os.path.abspath(tiff), survey.survey_dir)
    #         img.orig_name = tiff
    #         img.tiff_page = page
    #         print('Images added :'+str(img.filename)+str(img.orig_name)+str(img.tiff_page))
    #
    #     while images:
    #         # Simply drop the list of images again.
    #         sheet.images = []
    #
    #         add_image(survey, *tmptiff.pop(0))
    #         print(survey.defs.duplex)
    #         if survey.defs.duplex:
    #             add_image(survey, *tmptiff.pop(0))
    #         print(sheet.images)
    #         sheet.recognize.recognize()
    #
    #         for img in sheet.images:
    #             print(img.orig_name, img.tiff_page)
    #             print('\tPage:', img.page_number)
    #             print('\tRotated:', img.rotated)
    #             print('\tMatrix (px to mm):', img.raw_matrix)
    #             print('\tSurvey-ID:', sheet.survey_id)
    #             print('\tGlobal-ID:', sheet.global_id)
    #             print('\tQuestionnaire-ID:', sheet.questionnaire_id)
    #             print()
    #     surveyid = barcodeDetect(tempd + '/' + image)[0]
    #     facturation = barcodeDetect(tempd + '/' + image)[1]
    #     print(surveyid)
    #     if surveyid in surveyIdList:
    #         projectname = surveyIdList[surveyid]
    #         print (image+' found with '+surveyid+' ID, adding do the '+projectname)
    #         subprocess.call(['cp', tempd+'/'+scan, processedd+'/'+surveyid+".tif"])
    #         subprocess.call(['sdaps', 'add', projectname, tempd+'/'+image, '--convert'])
    #         subprocess.call(['sdaps', 'recognize', projectname])
    #         subprocess.call(['sdaps', 'csv', 'export', projectname])
    #         newrow = [facturation , surveyid , datetime.datetime.now() ]
    #         processedList.append(newrow)
    #
    # with open('processedList.csv', 'w', newline='') as f:
    #     wr = csv.writer(f, quoting=csv.QUOTE_ALL)
    #     wr.writerow(processedList)
    #
    # #cleaning
    # for scan in scans:
    #     os.remove(cmdline['scanFolder']+'/'+scan)
    # shutil.rmtree(tempd)
