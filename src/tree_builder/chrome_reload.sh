#!/bin/bash

# Chrome Refresh
#
# nik cubrilovic - nikcub.appspot.com
#
# Simple applescript browser reloader for Google Chrome. It will either open a 
# new tab with the url passed in as an argument or refresh an existing tab. 
#
# Link this up with watchr to auto-refresh browser windows when you save files
# or bind it in vim, textmate etc.
#
# example install:
#
# [nik@nikcub ~] $ echo $PATH
# /Users/nik/bin:/opt/local/bin:/opt/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/usr/X11/bin
# [nik@nikcub ~] $ cd ~/bin/
# [nik@nikcub ~/bin] $ ln -s ~/Projects/applescript/chrome-refresh.sh cr
# [nik@nikcub ~/bin] $ cr localhost:3333/admin/posts
# 13:53:35 Opening http://localhost:3333/admin/posts
#
# link to watchr:
#
# [nik@nikcub ~/bin] $ watchr -e "watch( '\w+/.*\.py' ) { system('cr localhost:3333') }"
# (edit a file and save..)
# 14:00:23 Opening http://localhost:3333
#
# watchr is easy to install:
#
# [nik@nikcub ~] $ sudo gem install watchr
#
# 2-clause BSD license all this, do what you want with it.
#


URL=$1
TS=$(date +"%H:%M:%S")

if [ "$URL" = "" ]; then 
  URL="http://localhost:3333/"
fi

if [ "${URL:0:7}" != 'http://' -a "${URL:0:8}" != 'https://' ]; then
  # set as https here if req
  URL="http://${URL}"
fi
URL="file:///Users/klessinger/axc/documentation/axc25/docs/swisscom/foo.html"
echo "$TS Opening $URL"

/usr/bin/osascript > /dev/null <<__ASCPT__
tell application "Google Chrome Canary"
	activate
	set theUrl to "${URL}"
	
	if (count every window) = 0 then
		make new window
	end if
	
	set found to false
	set theTabIndex to -1
	repeat with theWindow in every window
		set theTabIndex to 0
		repeat with theTab in every tab of theWindow
			set theTabIndex to theTabIndex + 1
			if theTab's URL = theUrl then
				set found to true
				exit
			end if
		end repeat
		
		if found then
			exit repeat
		end if
	end repeat
	
	if found then
		tell theTab to reload
		set theWindow's active tab index to theTabIndex
		set index of theWindow to 1
	else
		tell window 1 to make new tab with properties {URL:theUrl}
	end if
end tell
__ASCPT__
