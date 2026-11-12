# Δημιουργεί το task "PC Deals Relay": κάθε ώρα (:05) σαρώνει Plaisio / U-Case / Κωτσόβολο
# (μπλοκάρουν τους servers του GitHub) και ανεβάζει τα προϊόντα στο branch "relay". Δεν στέλνει email.
# Εκτέλεση:  powershell -ExecutionPolicy Bypass -File install_relay_task.ps1
# Αφαίρεση:  schtasks /delete /tn "PC Deals Relay" /f
$dir = $PSScriptRoot
$py = (Get-Command pythonw.exe -ErrorAction Stop).Source
$a = New-ScheduledTaskAction -Execute $py -Argument "`"$dir\pc_deals.py`" --relay --log `"$dir\logs\relay.log`"" -WorkingDirectory $dir
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 1)
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -MultipleInstances IgnoreNew `
     -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "PC Deals Relay" -Action $a -Trigger $t -Settings $s -Force `
    -Description "pc-deals: Plaisio/U-Case/Kotsovolos -> branch relay (χωρίς email)" | Out-Null
Get-ScheduledTaskInfo -TaskName "PC Deals Relay" | Select-Object TaskName, NextRunTime
