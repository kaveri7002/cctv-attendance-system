function getCameraErrorMessage(error) {
    if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
        return 'Camera permission is blocked. Allow camera access for this site, then reload the page.';
    }
    if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        return 'No camera was found. Connect or enable a camera, then reload the page.';
    }
    if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
        return 'The camera could not start. Close other apps using it and check the camera privacy shutter.';
    }
    if (error.name === 'OverconstrainedError') {
        return 'That camera could not be opened. Select another camera from the list.';
    }
    return 'The camera could not be opened. Check browser permissions and camera settings.';
}

async function startSelectableCamera(video, selector, onReady, onError, facingMode) {
    let activeStream;
    let switching = false;

    const refreshDevices = async (stream) => {
        const devices = (await navigator.mediaDevices.enumerateDevices())
            .filter((device) => device.kind === 'videoinput');
        const activeDeviceId = stream.getVideoTracks()[0]?.getSettings().deviceId;
        selector.replaceChildren();
        devices.forEach((device, index) => {
            const option = document.createElement('option');
            option.value = device.deviceId;
            option.textContent = device.label || `Camera ${index + 1}`;
            selector.appendChild(option);
        });
        if (activeDeviceId && devices.some((device) => device.deviceId === activeDeviceId)) {
            selector.value = activeDeviceId;
        }
        selector.disabled = devices.length < 2;
    };

    const openCamera = async (deviceId = '') => {
        switching = Boolean(activeStream);
        try {
            const videoConstraint = deviceId
                ? { deviceId: { exact: deviceId } }
                : (facingMode ? { facingMode: { ideal: facingMode } } : true);
            const stream = await navigator.mediaDevices.getUserMedia({
                video: videoConstraint,
                audio: false,
            });
            const previousStream = activeStream;
            video.srcObject = stream;
            try {
                await video.play();
            } catch (error) {
                stream.getTracks().forEach((track) => track.stop());
                video.srcObject = previousStream || null;
                throw error;
            }
            activeStream = stream;
            previousStream?.getTracks().forEach((track) => track.stop());
            await refreshDevices(stream);
            onReady(stream, stream.getVideoTracks()[0]?.label || 'Camera');
        } catch (error) {
            if (activeStream) {
                const activeDeviceId = activeStream.getVideoTracks()[0]?.getSettings().deviceId;
                if (activeDeviceId) {
                    selector.value = activeDeviceId;
                }
            }
            onError(error, switching, Boolean(activeStream));
        } finally {
            switching = false;
        }
    };

    selector.addEventListener('change', () => {
        if (selector.value) {
            openCamera(selector.value);
        }
    });
    await openCamera();
    return () => activeStream?.getTracks().forEach((track) => track.stop());
}

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
    const captureButton = document.getElementById('captureBtn');
    const submitButton = document.getElementById('submitBtn');
    const previewBox = document.getElementById('capturePreview');
    const form = document.getElementById('studentForm');
    const messageBox = document.getElementById('messageBox');
    const capturedImages = [];
    let registrationCameraReady = false;

    if (camera) {
        const cameraSelector = document.getElementById('registrationCamera');
        startSelectableCamera(
            camera,
            cameraSelector,
            (_stream, label) => {
                registrationCameraReady = true;
                messageBox.textContent = `Camera ready: ${label}.`;
            },
            (error, switching, hasActiveStream) => {
                registrationCameraReady = hasActiveStream;
                messageBox.textContent = switching
                    ? `${getCameraErrorMessage(error)} The previous camera is still selected.`
                    : getCameraErrorMessage(error);
            },
        ).then((stopCamera) => {
            window.addEventListener('pagehide', stopCamera, { once: true });
        });
    }

    if (captureButton && camera) {
        captureButton.addEventListener('click', () => {
            if (!registrationCameraReady || camera.videoWidth === 0 || camera.videoHeight === 0) {
                messageBox.textContent = 'Wait for camera access, then try capturing the face again.';
                return;
            }

            const canvas = document.getElementById('snapshotCanvas');
            const context = canvas.getContext('2d');
            context.drawImage(camera, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
            capturedImages.push(dataUrl);

            const img = document.createElement('img');
            img.src = dataUrl;
            img.alt = `Captured face ${capturedImages.length}`;
            previewBox.appendChild(img);
            messageBox.textContent = `Face image ${capturedImages.length} captured successfully.`;
        });
    }

    if (submitButton && form) {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (capturedImages.length === 0) {
                messageBox.textContent = 'Capture at least one face image before saving the student.';
                return;
            }

            const formData = new FormData(form);
            const payload = {
                student: Object.fromEntries(formData.entries()),
                images: capturedImages,
            };

            submitButton.disabled = true;
            submitButton.textContent = 'Saving...';
            messageBox.textContent = 'Saving student and processing the face image...';
            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload),
                });
                const contentType = response.headers.get('content-type') || '';
                const result = contentType.includes('application/json')
                    ? await response.json()
                    : null;

                if (!response.ok) {
                    messageBox.textContent = result?.error ||
                        `The server could not save the student (HTTP ${response.status}). Please try again.`;
                    return;
                }

                if (!result?.success) {
                    messageBox.textContent = result?.error || 'The server did not confirm the registration.';
                    return;
                }

                messageBox.textContent = result.message;
                form.reset();
                previewBox.innerHTML = '';
                capturedImages.length = 0;
            } catch {
                messageBox.textContent = 'Could not contact the server. Check your connection and try again.';
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = 'Save Student';
            }
        });
    }

    const statusName = document.getElementById('statusName');
    const statusId = document.getElementById('statusId');
    const statusConfidence = document.getElementById('statusConfidence');
    if (statusName && statusId && statusConfidence) {
        const liveVideo = document.getElementById('cameraFeed');
        const liveCameraSelector = document.getElementById('liveCamera');
        const frameCanvas = document.getElementById('frameCanvas');
        const liveMessage = document.getElementById('liveMessage');
        const statusDetail = document.getElementById('statusDetail');
        const canvasContext = frameCanvas.getContext('2d');
        let cameraStream;
        let processingFrame = false;

        const updateStatus = (status) => {
            statusName.textContent = status.name || 'Unknown';
            statusId.textContent = status.student_id ? `ID: ${status.student_id}` : 'ID: -';
            statusConfidence.textContent = `Confidence: ${Number(status.confidence || 0).toFixed(2)}`;
            statusDetail.textContent = status.status || status.error || '';
            if (liveMessage && status.error) {
                liveMessage.textContent = status.error;
            }
        };

        const processFrame = async () => {
            if (!cameraStream || processingFrame || liveVideo.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
                return;
            }

            processingFrame = true;
            try {
                const scale = Math.min(1, 640 / liveVideo.videoWidth, 480 / liveVideo.videoHeight);
                frameCanvas.width = Math.round(liveVideo.videoWidth * scale);
                frameCanvas.height = Math.round(liveVideo.videoHeight * scale);
                canvasContext.drawImage(liveVideo, 0, 0, frameCanvas.width, frameCanvas.height);
                const blob = await new Promise((resolve) => frameCanvas.toBlob(resolve, 'image/jpeg', 0.75));
                if (!blob) {
                    throw new Error('Could not capture an image from the camera.');
                }

                const response = await fetch('/api/process_frame', {
                    method: 'POST',
                    headers: { 'Content-Type': 'image/jpeg' },
                    body: blob,
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || 'Could not process the camera image.');
                }
                updateStatus(result);
                if (liveMessage) {
                    liveMessage.textContent = result.confirmed_frames && result.confirmed_frames < 3
                        ? `Confirming face: ${result.confirmed_frames} of 3 frames`
                        : result.status;
                }
            } catch (error) {
                if (liveMessage) {
                    liveMessage.textContent = error.message || 'Camera frame processing failed.';
                }
            } finally {
                processingFrame = false;
            }
        };

        let frameTimer;
        startSelectableCamera(
            liveVideo,
            liveCameraSelector,
            (stream, label) => {
                cameraStream = stream;
                if (liveMessage) {
                    liveMessage.textContent = `Camera connected: ${label}. Looking for a registered student…`;
                }
                if (!frameTimer) {
                    frameTimer = window.setInterval(processFrame, 1000);
                }
            },
            (error, _switching, hasActiveStream) => {
                const reason = getCameraErrorMessage(error);
                if (liveMessage) {
                    liveMessage.textContent = hasActiveStream
                        ? `${reason} The previous camera is still connected.`
                        : reason;
                }
                if (!hasActiveStream) {
                    updateStatus({ name: 'Camera unavailable', status: reason });
                }
            },
            'user',
        ).then((stopCamera) => {
            window.addEventListener('pagehide', () => {
                window.clearInterval(frameTimer);
                stopCamera();
            }, { once: true });
        });
    }
});
