not so easy to run CERN-VirtualBox-Tasks on BOINC. You have to work out a good balance on your machine(s) between your Projects

This checklist is the intention to help and was first developed for Atlas. But meanwhile you can also use this checklist for the other VM-Projects of LHC@Home, but Memory-Usage and Hardcopys are different.

As BOINC doesn't allow us to keep the original-checklist up to date, we have to make a new thread from time to time. This Version is actualized with all new informations / hints we got since the first checklist was made. This checklist was last updated at 06.06.2017

Because of these Checklist-Updates it may be that the numbering may change / has already changed. To be sure that you point / get pointed to the correct detail I suggest to set the Version-Number of the Checklist in Front. So V3.P5 is Checklist 3 (this one here) Point 5

Please, check this list and be sure to check really all Details, step by step, all are important.


Do you use an actual BOINC-x64-Client ? At the Moment, 7.6.22, 7.6.33 or 7.8.3 does it very well. At 09.08.2018 I have started to test 7.12.1 and it seems to be fine.

VirtualBox

Do you have installed VirtualBox ? At the Moment, 5.1.30 is doing very well, Atlas-Team even recommends to use them. Atlas has stopped working on VirtualBox 4.x

WIN10-Users should use 5.1.16 (or higher ones), as the upcoming 17xx-release is pronounced not to work with older VirtulBox-Versions

At the moment I'm (09.08.2018) I'm trying 5.2.16 (together with BOINC 7.12.1) and it seems also to work fine with Atlas (I'm on Win10 1803)

Do you use Hyper-V or Docker ? They will interfere with VirtualBox and cause problems. You should deactivate, better uninstall them

You should install the ExtensionPack according to your VirtualBox-Version. So, if you are running VirtualBox 5.1.16, you should install the ExtensionPack for 5.1.16. This will enable you to solve possible problems

Check, if (Intel = VT-X / AMD = AMD-v (former SVM-Mode) / VIA = VIA-vt) in your BIOS is switched on. To check you can use a great tool from the web. Download LeoMoon CPU-V and check if it gives you 2 green okays.

If you updated your BIOS or upgraded memory of your machine it may happen that VT-X / AMD-V / VIA-VT got switched off and you have to re-enable it. And then you will surely have to check the next point

Did you try to crunch Projects using VMs in the past while VT-X / AMD-V / VIA-VT was not enabled? Could be that BOINC has kept this in mind!

To check and fix this, first exit BOINC and make sure, all BOINC-Tasks have really finished.

In your BOINC_Data-Directory you will find a client_state.xml. Open this with a simple editor and search for:
[pre]
<p_vm_extensions_disabled>1</p_vm_extensions_disabled>[/pre]
If this is absent or the number is 0 / zero than all is fine. Otherwise change it to 0 / zero <p_vm_extensions_disabled>0</p_vm_extensions_disabled> and safe the file. Be carefull to save it as a real ascii-file

Be carefull that you closed your BOINC-Client successfully before you change anything in client_state.xml. Otherwise BOINC will overwrite your changes

Local Resources

Check, if you have have enough RAM for Atlas available. Each SingeCore-Atlas-Task needs 2,1 GB free RAM, MultiCore-WUs need 3,0 GB + 0,9 GB * number of cores (Last Update from 01.08.2018) So 7,5 GB for a 5-Core WU.

[Update 18.09.2018] Nowerdays Atlas runs only MultiCoreWUs, even if you run it with 1-Core only it will need up to 3,9 GB as SingleCore

If you have an 8-core-processor, but only 8 GB RAM, BOINC will try to satisfy all 8 cores, this will lead to a point where one or more or all VMs get stalled with "postponed: waiting for memory ..."

If you get messages like these you should first try to run only 1 WU and see, if this works well. If so, enable a second one and look how it works. And so on. If you have "postponed: waiting for memory ..." WUs sitting in your BOINC-Client you could exit BOINC and restart it after a short pause.

Meanwhile Atlas focusses on MultiCoreWU, so one WU can use more than 1 core to crunch. Atlas is capabable from 1 to 8 core /WU. You can set the number of cores you want on the project-preferences. Set the "Number of Cores" to your wishes. Note, that this only works for newly downloaded WUs. Consider aborting already downloaded WUs.

Check, if you have enough disk-spcae and allowed BOINC to use them. You will find this in your Preferences

Check that your Windows-Firewall lets the communication work. BOINC.EXE and VBoxHeadless.exe need out- and incoming communications.

Check that your AntiVirus ignores your BOINC_Data-Directory

Try to run only 1 Atlas at a time until you got it succesfull working
..... A) You can suspend the other Tasks manually
..... B) you can use an app_config.xml

Atlas connects on different ports to their Servers as BOINC-Users are used. You will have to open these ports:
..... HTTP (Port 80)
..... HTTP Proxy (Port 3128)
..... HTTPS (Port 443)
..... XMPP (Port 5222)
..... TCP Port 9094

There is a new page that gives you official Information from Project_team

If all this is ok, you should be ready to start.




For your understanding: When an Atlas-Task starts up, it first connects to External-CERN-Servers to fetch actual Knowledge / Figures from there. Depending on the speed of your Internet-Connection this can take some time and this time may vary. This is why you had to open the ports in V3.P10

BOINC isn't really good running MultiCore- and Single-Core-WUs together. If you want this to do, be prepared that you have to make a lot and difficult work to find a reliable Balance on your machine(s)

If you are having trouble with Atlas-WUs, it is a good idea to run Atlas-Only for a limited time, until you are sure, all works fine as it should.

If you run a Task, you can mark it in BOINC and check the Properties. Interesting for you is "CPU-Time at last checkpoint" versus "CPU-Time". For SingleCore-WUs they should have only a small difference of 10 to 20 minutes. A simple example from my box is: 01:04:09 versus 01:22:26. This is 8 minutes difference and this is okay. If there are big differences something seems to be wrong.

With MultiCore-WUs after startup-sequence (Point Nr 12 / V3.P12) CPU-Time should climb much faster than elapsed-time. So with a 5-Core-WU 01:00:00 hour elapsed time and 04:50:00 hours CPU-Time is okay

With latest Atlas I have seen no simply longrunner among thousands of crunched WUs. My slowest PC has done a Task in max 12 hours, my fastest do it in 01:04 or usually in 1 hour 40/50 minutes.

Note: Actual one Atlas-WU contains 100 Jobs to be done. From Time to Time the project-team changes the number of Jobs based on their needs, so Runtime my vary and you should take a look around how many Jobs are actual in your WU(s)

If your WUs seem to start up fine, we can get following scenarios:


Scenario A:

Your WUs end up after 10 or 20 minutes then there could something still be wrong mostly on your PC or your Firewall.

Scenario B:

Your WUs run more than 20 / 30 minutes but your CPU-Time is only 10 or 20 seconds, then we do not know exactly what is the reason.

In one case we could identify a faulty DNS-Server as reason.

You could help us to find the reason for this. First try a project reset of Atlas (LHC@Home).

If this helped: fine! Let us know

If this didn't help maybe you should consider to clean up the install as described in the last point

Scenario C:

Your WUs end up after several seconds. In the logs you can find something like "Error Code: ERR_CPU_VM_EXTENSIONS_DISABLED"

Then you should go back to Point Nr 4 (V3.P4) + 5 (V3.P5) above

Scenario D:

Your WUs get stalled with "postponed: waiting for memory ...". Most of the time you have tried to start more WUs than the memory of your Machine can stand. Suspend several of these WUs, exit BOINC and make sure all tasks are ended, then start BOINC again. Try to run 1 task only to see if that works, than 2 and so on.

May be you should check your settings about memory at https://lhcathome.cern.ch/lhcathome/prefs.php?subset=global&cols=1. Check for "memory when computer is in use"

Scenario E:

Your WU runs and runs and runs and you are afraid you have a dead longrunner. Then you should go inside the VM Console (see below), click with the mouse into the Console and enter a Username at the Login-Prompt. Try Atlas as username and press enter.

If you get the Password-Prompt, all seems to be fine and the VM seems to be still alive.

If you don't get the Password-Prompt within 5 / 10 seconds, than the WU seems to be crashed and you should abort it

------------------------------------------------------------------------

Another way to check your WU is to mark the running WU in TASKS and then klick on the PROPERTIES-BUTTON at the left side.

You will get a windows similar like this:



The example is a running 3-Core-WU. You should check:

CPU-Time at last checkpoint
CPU-Time
Elapsed Time

CPU-Time should be something about "Elapsed Time" * NumberOfCores - 15 minutes

If CPU-Time is something with 1 or 2 hours but your Elapsed-Time is already much higher, than the WU is dead and you should abort it


If you think, somethink is still not right, you can take a look inside the VM (That's why we asked you to install the extension pack).
..... Mark the running AtlasJob in BOINC-Manager
..... Choose "Show VM Console" in the left side.
..... A console should open showing following lines (with Atlas 1.44)



If your Console looks like this, all seems fine and your WU should finish succesfull soon

Meanwhile you can see more details within the console. Put your mouse over the console-windows, klick into the window and then press ALT/F2. Then you should see some output from your running tasks:

ATLAS ALT/F2:



ATLAS ALT/F3: (~ TOP-SCREEN) This screen shows a running 3-Core-WU. Look at CPU%




ATLAS ALT/F3: example for a DEAD WU (it should run as an 1-Core-WU, you can see that it really is running as an 8-Core-WU)



Theory:

Hardcopy follows

CMS ALT/F1:



CMS ALT/F2:



CMS ALT/F3: (~ TOP-SCREEN)



LHCb:

Hardcopy follows

Alice:

Hardcopy follows



If you want to clean up your install:

Set Atlas-Project / LHC@Home to "No New Tasks"
Abort all Atlas/LHC@Home-Tasks in BOINC-Manager
Force BOINC to communicate with Atlas/LHC@Home-Server until all Tasks are gone in your task-list
Exit BOINC
Open VirtualBoxManager and delete all VMs that are listed (be carefull not to delete VMs of vLHC or CMS)
Exit VirtualBoxManager
Reboot your PC

Now you should be ready for a new try

In some circumstances it was necessary to completly deinstall VirtualBox / BOINC, reboot the PC and then re-install VirtualBox / BOINC
* Want to run MultiCore-WUs but you don't like the number of cores it takes?

No Problem, look in this thread how to reduce the number of cores MultiCore-WUs use

Still not working ? Post your problem here

Yeti



Supporting BOINC, a great concept !
