$(document).ready(function () {
    // Voice navigation code (unchanged)
    let navigationInterval = setInterval(checkNavigation, 3000);

    function checkNavigation() {
        $.ajax({
            url: '/check_navigation',
            type: 'GET',
            success: function (data) {
                if (data.command) {
                    console.log('Navigation command received: ' + data.command);
                    // Navigate to the specified page
                    window.location.href = '/' + data.command;
                }
            },
            error: function (error) {
                console.error('Error checking navigation:', error);
            }
        });
    }

    // Voice assistant start/stop buttons (unchanged)
    $('#startVoice').click(function () {
        $.post('/start_voice', function (data) {
            console.log('Voice assistant started');
            $('#voiceStatus').text('Voice assistant is active. Say "Hey Buddy" followed by a navigation command.');
        });
    });

    $('#stopVoice').click(function () {
        $.post('/stop_voice', function (data) {
            console.log('Voice assistant stopped');
            $('#voiceStatus').text('Voice assistant is inactive.');
        });
    });

    // Toggle Edit/Save functionality with enhanced debugging
    $('#toggle-edit').click(function () {
        if ($('#profile-form input:disabled, #profile-form select:disabled').length > 0) {
            // Enable editing (and enable search fields)
            $('#profile-form input, #profile-form select').prop('disabled', false);
            $('#search-disease-btn').prop('disabled', false);
            $(this).text('Save');
        } else {
            // Gather form data with extensive logging
            var data = {
                height: $('#height').val(),
                height_unit: $('#height_unit').val(),
                weight: $('#weight').val(),
                weight_unit: $('#weight_unit').val(),
                rare_diseases: $('#rare_diseases').val(), // Ensure this is the hidden field
                dob: $('#dob').val(), // expected in YYYY-MM-DD format
                gender: $('#gender').val(),
                nationality: $('#nationality').val(),
                zip_code: $('#zip_code').val(),
                email: $('#email').val(),
                phone: $('#phone').val(),
            };


            $.ajax({
                url: "{{ url_for('update_profile') }}",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify(data),
                success: function (response) {
                    console.log("Update Profile Success Response:", response);
                    
                    // Log the returned rare diseases to verify
                    console.log("Returned Rare Diseases:", response.rare_diseases);
                    
                    alert(response.message);
                    
                    // Disable inputs after saving (and disable search fields)
                    $('#profile-form input, #profile-form select').prop('disabled', true);
                    $('#search-disease-btn').prop('disabled', true);
                    $('#toggle-edit').text('Edit');
                    
                    // Update BMI and Age display
                    $('#bmi-display').text(response.bmi ? response.bmi : 'N/A');
                    $('#age-display').text(response.age !== null ? response.age : 'N/A');
                },
                error: function (xhr) {
                    // Log detailed error information
                    console.error("Error updating profile:", xhr.status);
                    console.error("Response Text:", xhr.responseText);
                    alert('Error updating profile. Check console for details.');
                }
            });
        }
    });

});