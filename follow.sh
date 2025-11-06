source venv/bin/activate

playerctl metadata --format '{{mpris:artUrl}}' --follow | while read -r ART_URL; do
    echo "Processing..."
    # Skip empty URLs
    if [[ -n "$ART_URL" ]]; then
        python3 main.py
        echo "Processing done."
    fi
done
