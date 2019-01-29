# [Flexget](http://www.flexget.com) Configuration Files

Created by: [Jeff Wilson](mailto:jeff@jeffalwilson.com)  
Available from: https://github.com/jawilson/flexget-config (originally located in https://github.com/jawilson/dotfiles)

Flexget Version: 2.18.8

Forked by: [Paul Cardamone](mailto:paul.cardamone@gmail.com)
This Fork is available at: (https://github.com/carda21/flexget-config)

Modified Jeff's great work to use Transmission instead of Deluge.  Also some tweaks to get this working with a local running flexget, accessing a seedbox with Transmission installed

## Installation
1. Install [Flexget](http://www.flexget.com)
1. Clone this repository into the `.flexget` directory of your home directory
    ```bash
    git clone https://github.com/carda21/flexget-config.git .flexget
    ```
1. Set up your `secretfile.yml`
1. Run the Flexget daemon
    ```bash
    flexget daemon start -d
    ```

I've also added the following line to my local crontab (`crontab -e`):
```
@reboot /usr/local/bin/flexget daemon start -d >/dev/null 2>&1
```

## Rar-unpacking

TBD
