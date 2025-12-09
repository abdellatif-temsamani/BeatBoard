send-keys -t :1 'git fetch --all && git pull ' C-m
# Window 1: Editor
rename-window -t :1 'Editor'
send-keys -t :1 'nvim' C-m

# Window 2: Local server, npm, and reverb
new-window -t :2 -n 'Server + Reverb'
send-keys -t :2 'php artisan serve' C-m

split-window -t :2 -h
send-keys -t :2.1 'npm run dev' C-m

split-window -t :2.1 -v
send-keys -t :2.2 'sleep 5 && php artisan reverb:start' C-m

new-window -t :3 -n 'Pail'
send-keys -t :3 'php artisan pail -vvv --timeout=0' C-m

split-window -t :3 -v

# Go back to the editor window
select-window -t :1

# vim: ft=tmux
