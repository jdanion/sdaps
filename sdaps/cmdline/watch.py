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

from sdaps import model
from sdaps import script
from sdaps import defs
from path import Path
import os, subprocess, tempfile, shutil
from pyzbar  import pyzbar
import argparse
import cv2

from sdaps.utils.ugettext import ugettext, ungettext
_ = ugettext

parser = script.add_project_subparser("watch",
    help=_("Watching for new scan commit"),
    description=_("""Watch in a specified folder to detect a new scan,
    convert and push it to the right project."""))

parser.add_argument('--scanFolder','-sf',
    help=_("Folder to be watched"))

parser.add_argument('--projectsFolder','-pf',
    help=_("Folder containing SDAPS projects"))

@script.connect(parser)
def watch(cmdline):

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
    scans = os.listdir(cmdline['scanFolder'])

    #temp folder creation
    tempd = tempfile.mkdtemp()

    #convert and copy
    for scan in scans:
        scan_title, scan_extension = os.path.splitext(scan)
        if scan_extension != '.tif' or scan_extension != '.tiff' and scan_extension == '.pdf':
            print('File', scan, 'found and converted')
            subprocess.call(['pdfimages', '-tiff', cmdline['scanFolder']+'/'+scan, tempd+'/'+scan_title])
        elif scan_extension == '.tif' or scan_extension == '.tiff':
            subprocess.call(['cp', cmdline['scanFolder']+'/'+scan, tempd+'/'+scan])
        else:
            print('Wrong image format')

    images = os.listdir(tempd)

    for image in images:
        id = barcodeDetect(tempd + '/' + image)[0:-4]
        if id in surveyIdList:
            project = surveyIdList[id]
            print ( image+' found with '+id+' ID, adding do the '+project)
            subprocess.call(['sdaps', 'add', project, tempd+'/'+image, '--convert'])
            subprocess.call(['sdaps', 'recognize', project])
            subprocess.call(['sdaps', 'csv', 'export', project])

    #cleaning
    for scan in scans:
        os.remove(cmdline['scanFolder']+'/'+scan)
    shutil.rmtree(tempd)


def barcodeDetect(image):

    # load the input image
    imageLoad = cv2.imread(image)

    # find the barcodes in the image and decode each of the barcodes
    barcodes = pyzbar.decode(imageLoad)

    # loop over the detected barcodes
    for barcode in barcodes:
        barcodeData = barcode.data.decode("utf-8")
        return barcodeData
