import subprocess
import logging
from typing import Optional

class AIHandler:
    def __init__(self, config: dict) -> None:
        self.enabled = config.get('ai_enabled', False)
        self.extensions = config.get('ai_enabled_extensions', [])
        self.command_template = config.get('ai_command', 'native')

    def get_new_filename(self, file_path: str) -> Optional[str]:
        if '.Screenshot' in file_path:
            file_path = file_path.replace('.Screenshot', 'Screenshot')
        if not self.enabled:
            return None
        
        if self.command_template == 'native':
            return self._get_native_description(file_path)

        try:
            command = self.command_template.replace('{file_path}', file_path)
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            output = result.stdout.strip()
            if output and output != file_path:
                return self._sanitize_filename(output)
                
        except (subprocess.CalledProcessError, Exception) as e:
            logging.error(f'AI cmd failed: {e}')
            
        return None

    def _get_native_description(self, file_path: str) -> Optional[str]:
        try:
            import Cocoa
            import Vision
            from Foundation import NSURL
            import objc
        except ImportError:
            return None

        try:
            image_url = NSURL.fileURLWithPath_(file_path)
            
            try:
                bundle_path = '/System/Library/Frameworks/Vision.framework'
                objc.loadBundle('Vision', bundle_path=bundle_path, module_globals=globals())
                
                VNRecognizeTextRequest = Vision.VNRecognizeTextRequest or objc.lookUpClass('VNRecognizeTextRequest')
                ocr_request = VNRecognizeTextRequest.alloc().init()
                ocr_request.setRecognitionLevel_(0)
                ocr_request.setUsesLanguageCorrection_(True)
                
                handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(image_url, None)
                success, error = handler.performRequests_error_([ocr_request], None)
                
                if success and ocr_request.results():
                    texts = []
                    for obs in ocr_request.results():
                        candidate = obs.topCandidates_(1)[0].string()
                        if len(candidate) > 3:
                            texts.append(candidate)
                        if len(texts) >= 3: break
                    
                    if texts:
                        full_text = '_'.join(texts)
                        return self._sanitize_filename(full_text)
            except Exception as e:
                logging.warning(f'Native OCR failed/empty: {e}')

            try:
                req_classify = Vision.VNClassifyImageRequest.alloc().init()
                handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(image_url, None)
                success, error = handler.performRequests_error_([req_classify], None)
                
                if success and req_classify.results():
                    top_results = req_classify.results()[:5]
                    logging.debug('Native Classification Results:')
                    for obs in top_results:
                        logging.debug(f' - {obs.identifier()}: {obs.confidence()}')

                    components = [obs.identifier().strip() for obs in top_results if obs.confidence() > 0.1]
                    if components:
                         return self._sanitize_filename('_'.join(components[:3]))
                    else:
                         logging.warning('No classifications met confidence threshold.')
            except Exception as e:
                logging.error(f'Native Classification failed: {e}')

            return None
        except Exception as e:
            logging.error(f'Native Vision analysis failed: {e}')
            return None

    def _sanitize_filename(self, text: str) -> str:
        safe_name = ''.join(c for c in text if c.isalnum() or c in (' ', '.', '_', '-')).strip()
        return safe_name[:50]
