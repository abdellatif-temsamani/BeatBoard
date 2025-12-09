send-keys -t :1 'git fetch --all && git pull ' C-m
# Window 1: Editor
rename-window -t :1 'Editor'
send-keys -t :1 'source venv/bin/activate' C-m
send-keys -t :1 'nvim' C-m
# vim: ft=tmux
