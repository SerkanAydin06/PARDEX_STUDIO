"""Command-line entry for a single concrete owner-reviewed AI change."""
import argparse
import json

import change_review
import project_delivery as delivery


def main(argv=None):
    parser = argparse.ArgumentParser(description='PARDEX: tek AI görevi, ayrı kopya, test, onay')
    parser.add_argument('--project', required=True, help='Godot/Unity/Flutter/Web vb. proje yolu')
    parser.add_argument('--goal', required=True, help='Tek somut görev açıklaması')
    parser.add_argument('--files', nargs='+', required=True, help='Değişmesine izin verilen dosya yolları')
    parser.add_argument('--provider', choices=['Codex', 'Claude', 'Gemini'], default='Codex')
    parser.add_argument('--minutes', type=int, default=15)
    parser.add_argument('--preview', action='store_true', help='Sadece plan, AI çağrısı yok')
    parser.add_argument('--confirm', action='store_true', help='Bu tek görevi başlatmayı onaylıyorum')
    parser.add_argument('--allow-native', action='store_true', help='Yerel CLI sandbox değildir; riskini kabul ediyorum')
    args = parser.parse_args(argv)
    if args.preview:
        result = delivery.preview(args.project, args.goal, args.files, provider=args.provider)
    else:
        result = delivery.deliver(args.project, args.goal, args.files, provider=args.provider,
                                  max_minutes=args.minutes, owner_confirms=args.confirm,
                                  allow_native_cli=args.allow_native)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if 'review_id' in result:
        print('\n--- İNCELEME FARKI (ilk 9000 karakter) ---')
        print(change_review.diff(result['review_id'], home=delivery.core.HOME / 'delivery_reviews' / 'reviews'))
        print('\nUygulama otomatik değildir. 07_AI_DEGISIKLIK_INCELE.cmd veya change_review_cli ile açıkça onayla.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
