# Anton Commands

## Wake (start everything)

launchctl load ~/Library/LaunchAgents/com.niranjan.anton.wake.plist

## Sleep (stop everything)

launchctl unload ~/Library/LaunchAgents/com.niranjan.anton.wake.plist

## Restart

launchctl unload ~/Library/LaunchAgents/com.niranjan.anton.wake.plist 2>/dev/null && launchctl load ~/Library/LaunchAgents/com.niranjan.anton.wake.plist

## Watch live log

tail -f ~/Library/Logs/anton-wake.log
