# ... existing code ...

# Replace the incorrect calls
initial_analysis = analyze_page_with_context(driver, {
    "sections": sections,
    "current_step": 1
})

post_apply_analysis = analyze_page_with_context(driver, {
    "sections": post_sections,
    "current_step": 2
})

post_upload_analysis = analyze_page_with_context(driver, {
    "sections": post_upload_sections,
    "current_step": 3
})

# ... existing code ... 