document.addEventListener('DOMContentLoaded', () => {
    const deleteButtons = document.querySelectorAll('[data-delete-id]');
    deleteButtons.forEach((button) => {
        button.addEventListener('click', async () => {
            const studentId = button.getAttribute('data-delete-id');
            const response = await fetch(`/api/delete_student/${studentId}`, { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                window.location.reload();
            } else {
                alert(result.error || 'Delete failed.');
            }
        });
    });

    const camera = document.getElementById('camera');
    if (camera) {
        navigator.mediaDevices.getUserMedia({ video: true, audio: false })
            .then((stream) => {
                camera.srcObject = stream;
            })
            .catch(() => {
                const box = document.getElementById('messageBox');
                if (box) {
                    box.textContent = 'Camera access is required to register students.';
                }
            });
    }

    const captureButton = document.getElementById('captureBtn');
    const submitButton = document.getElementById('submitBtn');
    const previewBox = document.getElementById('capturePreview');
    const form = document.getElementById('studentForm');
    const messageBox = document.getElementById('messageBox');
    const capturedImages = [];

    if (captureButton && camera) {
        captureButton.addEventListener('click', () => {
            const canvas = document.getElementById('snapshotCanvas');
            const context = canvas.getContext('2d');
            context.drawImage(camera, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
            capturedImages.push(dataUrl);

            const img = document.createElement('img');
            img.src = dataUrl;
            previewBox.appendChild(img);
            messageBox.textContent = 'Face image captured successfully.';
        });
    }

    if (submitButton && form) {
        submitButton.addEventListener('click', async () => {
            const formData = new FormData(form);
            const payload = {
                student: Object.fromEntries(formData.entries()),
                images: capturedImages,
            };

            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
            const result = await response.json();

            if (result.success) {
                messageBox.textContent = result.message;
                form.reset();
                previewBox.innerHTML = '';
                capturedImages.length = 0;
            } else {
                messageBox.textContent = result.error || 'Registration failed.';
            }
        });
    }

    const statusName = document.getElementById('statusName');
    const statusId = document.getElementById('statusId');
    const statusConfidence = document.getElementById('statusConfidence');
    if (statusName && statusId && statusConfidence) {
        setInterval(async () => {
            const response = await fetch('/api/live_status');
            const status = await response.json();
            statusName.textContent = status.name || 'Unknown';
            statusId.textContent = status.student_id ? `ID: ${status.student_id}` : 'ID: -';
            statusConfidence.textContent = `Confidence: ${Number(status.confidence || 0).toFixed(2)}`;
        }, 1500);
    }
});
