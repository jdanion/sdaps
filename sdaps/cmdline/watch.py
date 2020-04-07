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

import os, subprocess, tempfile, shutil, sys
from sdaps import convert
from sdaps import script
from sdaps import recognize
from sdaps import model
from sdaps import image
from sdaps.utils import opencv
from path import Path
from PIL import Image
from PIL import TiffImagePlugin

import argparse
import datetime
import csv

from sdaps.utils.ugettext import ugettext, ungettext

_ = ugettext

parser = script.add_project_subparser("watch",
                                      help=_("Watching for new scan commit"),
                                      description=_("""Watch in a specified folder to detect a new scan,
    convert and push it to the right project."""))

parser.add_argument('--scanFolder', '-sf',
                    help=_("Folder to be watched"))

parser.add_argument('--projectsFolder', '-pf',
                    help=_("Folder containing SDAPS projects"))

parser.add_argument('--renamedFolder', '-rf',
                    help=_("Folder with renamed and processed scans"))


@script.connect(parser)
def watch(cmdline):

    global tiffname

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

    # temp folder creation
    tempd = tempfile.mkdtemp()
    print('Temp folder :' + tempd)

    if os.path.exists('./WATCH/info'):
        print('WATCH project found, processing')
        pass
    else:
        print('Creating new WATCH project')
        subprocess.call(['sdaps', 'setup', 'WATCH', './watch.tex'])
    watchtexpath = (os.path.dirname(os.path.abspath(__file__)))

    # loading dummy survey
    print('Loading WATCH project')
    survey = model.survey.Survey.load('WATCH')

    # A sheet object to attach the images to
    sheet = model.sheet.Sheet()
    survey.add_sheet(sheet)

    print('Listing all projects in ProjectsFolder')

    # creating project dictionnary
    surveyIdList = {}

    # folder with already processed scans
    renamedFolder = cmdline['renamedFolder']
    surveysRenamedFolder = os.listdir(renamedFolder)

    print(surveysRenamedFolder)

    # list of all subfolders containing 'info'
    for file in Path(cmdline['projectsFolder']).walkfiles('info'):
        s = file.dirname()
        with open(s + '/info', "r") as infoFile:
            # looking for survey id and add it to the dictionary
            lines = infoFile.read()
            line = lines.split('\n')
            for l in line:
                words = l.split(' = ')
                if words[0] == 'survey_id':
                    print('DETECT : ' + words[1])
                    surveyIdList[words[1]] = s
    with open('surveyList.csv', 'w') as f:
        for key in surveyIdList.keys():
            f.write("%s,%s\n" % (key, surveyIdList[key]))
            subprocess.call(['mkdir', tempd + '/' + key])
            if key not in surveysRenamedFolder:
                subprocess.call(['mkdir', cmdline['renamedFolder'] + '/' + key])
            else:
                print('Folder ' + key + ' already exist')


    # file retrieval
    print('Listing scanned files')
    scans = os.listdir(cmdline['scanFolder'])

    # convert and copy
    for scan in scans:
        scan_title, scan_extension = os.path.splitext(scan)
        print(scan_title, scan_extension)
        if is_pdf(scan):
            print('PDF file found')
            print('Scan title ' + scan_title, 'Scan extension ' + scan_extension)
            tempscanpdf = tempfile.mktemp(suffix='.pdf', dir=tempd)
            tempscantif = tempfile.mktemp(suffix='.tif', dir=tempd)
            print('File', str(cmdline['scanFolder'] + '/' + scan), 'found, trying to convert to ' + tempscantif)
            subprocess.call(['cp', cmdline['scanFolder'] + '/' + scan, tempscanpdf])
            print('Copied ' + str(cmdline['scanFolder'] + '/' + scan) + ' to ' + tempscanpdf)
            convert.convert_images([tempscanpdf], tempscantif, survey.defs.paper_width, survey.defs.paper_height)
        elif is_tiff(scan):
            print('TIFF file found')
            tempscantif = tempfile.mktemp(suffix='.tif', dir=tempd)
            subprocess.call(['cp', cmdline['scanFolder'] + '/' + scan, tempscantif])
        else:
            print('Wrong image format for file ' + scan + ', ignoring')

    # we retrieve all tiff to be processed
    tiffscans = filter(is_tiff, os.listdir(tempd))

    images = []

    for file in tiffscans:
        num_pages = image.get_tiff_page_count(tempd + '/' + file)
        # Create one tif file for every pages and add it into images dict
        #subprocess.call(['convert', tempd + '/' + file, tempd + '/%d' + file])
        tifs = Image.open(tempd + '/' + file)
        for page in range(num_pages):
            print(tempd + '/' + str(page) + file)
            # Reconvert each tif to the survey format
            try:
                tifs.seek(page)
                tifs.save(tempd + '/' + str(page) + file)
            except EOFError:
                break
            convert.convert_images([tempd + '/' + str(page) + file], tempd + '/' + str(page) + file, survey.defs.paper_width, survey.defs.paper_height)
            images.append((tempd + '/' + str(page) + file, 1))

    if len(images) == 0:
        # No images, simply exit again.
        print('No scans found')
        sys.exit(1)

    def add_image(survey, tiff, page):
        img = model.sheet.Image()
        survey.sheet.add_image(img)
        # SDAPS assumes a relative path from the survey directory
        img.filename = os.path.relpath(os.path.abspath(tiff), survey.survey_dir)
        img.orig_name = tiff
        img.tiff_page = page
        # print('Images added :'+str(img.filename)+str(img.orig_name)+str(img.tiff_page))
        imgdummy = model.sheet.Image()
        survey.sheet.add_image(imgdummy)
        imgdummy.orig_name = "DUMMY"
        imgdummy.filename = "DUMMY"
        imgdummy.tiff_page = -1
        imgdummy.ignored = True
        # print('Images added :'+str(imgdummy.filename)+str(img.orig_name)+str(imgdummy.tiff_page))

    while images:
        # Simply drop the list of images again.
        sheet.images = []

        add_image(survey, *images.pop(0))
        print('Adding image simplex mode')

        if survey.defs.duplex:
            print('Adding image duplex mode')
            add_image(survey, *images.pop(0))

        # print(images)

        print('Adding image in the correct survey ')

        sheet.recognize.recognize()

        for img in sheet.images:
            if img.tiff_page != -1:
                print(img.orig_name, img.tiff_page)
                print('\tPage:', img.page_number)
                print('\tRotated:', img.rotated)
                print('\tMatrix (px to mm):', img.raw_matrix)
                print('\tSurvey-ID:', sheet.survey_id)
                if hasattr(sheet, 'barecode_id'):
                    print('\tBarcode-ID:', sheet.barecode_id)
                print('\tGlobal-ID:', sheet.global_id)
                print('\tQuestionnaire-ID:', sheet.questionnaire_id)
                now = datetime.datetime.now()
                datestamp = now.strftime('%Y%m%d%H%M%S%f')

                tiffname = str(renamedFolder) + '/' + str(sheet.survey_id) + '/DATE' + str(datestamp) + 'QID' +\
                           str(sheet.questionnaire_id) + str(img.page_number) + 'SRVID' + str(sheet.survey_id)

            subprocess.call(['cp', img.orig_name, tiffname + ".tif"])
            subprocess.call(['cp', img.orig_name, tempd + '/' + str(sheet.survey_id) + '/' + str(sheet.questionnaire_id)\
                             + str(sheet.survey_id) + str(img.page_number) + ".tif"])

    # merge of tif files in each survey directory into one file for analyse
    for survey in surveyIdList:
        tifs = os.listdir(tempd + '/' + survey)
        with TiffImagePlugin.AppendingTiffWriter(tempd + '/' + survey + '.tif', True) as tf:
            for tiff_in in tifs:
                try:
                    im = Image.open(tempd + '/' + survey + '/' + tiff_in)
                    im.save(tf)
                    tf.newFrame()
                    im.close()
                except:
                    sys.exit(0)

        # recognize each survey
        subprocess.call(['sdaps', 'add', surveyIdList[survey], tempd + '/' + survey + '.tif', '--convert'])
        subprocess.call(['sdaps', 'recognize', surveyIdList[survey]])
        subprocess.call(['sdaps', 'csv', 'export', surveyIdList[survey]])

    # cleaning
    print('Removing temporary directory')
    shutil.rmtree(tempd)
    for scan in scans:
        print('Removing scan : ' + scan)
        os.unlink(cmdline['scanFolder'] + '/' + scan)
