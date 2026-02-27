#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREMIUM STORE - License Verification API
Railway.app üzerinde çalışır
"""

from flask import Flask, request, jsonify
import os
import json
import requests
from datetime import datetime
import base64

app = Flask(__name__)

# Environment Variables (Railway'de ayarlanacak)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')  # Örnek: username/repo-name
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')

# GitHub API Base URL
GITHUB_API = "https://api.github.com"


def get_github_file(filename):
    """GitHub'dan dosya oku"""
    try:
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{filename}?ref={GITHUB_BRANCH}"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content), data['sha']
        
        print(f"❌ GitHub okuma hatası: {filename} - Status {response.status_code}")
        return None, None
    except Exception as e:
        print(f"❌ GitHub okuma exception: {e}")
        return None, None


def update_github_file(filename, content, sha, commit_message):
    """GitHub'a dosya yaz"""
    try:
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        content_encoded = base64.b64encode(json.dumps(content, indent=2).encode('utf-8')).decode('utf-8')
        
        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{filename}"
        payload = {
            "message": commit_message,
            "content": content_encoded,
            "sha": sha,
            "branch": GITHUB_BRANCH
        }
        
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            print(f"✅ GitHub güncelleme başarılı: {filename}")
            return True
        else:
            print(f"❌ GitHub yazma hatası: {filename} - Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ GitHub yazma exception: {e}")
        return False


@app.route('/')
def home():
    """API ana sayfa"""
    return jsonify({
        "status": "online",
        "service": "PREMIUM STORE License Verification API",
        "version": "2.1.0",
        "platform": "Railway"
    })


@app.route('/verify', methods=['POST'])
def verify_license():
    """Lisans doğrulama endpoint'i"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "message": "Geçersiz istek"}), 400
        
        license_key = data.get('license_key')
        username = data.get('username')
        hwid = data.get('hwid')
        
        print(f"\n{'='*60}")
        print(f"🔥 Gelen İstek:")
        print(f"   License: {license_key}")
        print(f"   User: {username}")
        print(f"   HWID: {hwid}")
        print(f"{'='*60}\n")
        
        if not license_key or not username or not hwid:
            return jsonify({
                "success": False,
                "message": "Eksik parametreler"
            }), 400
        
        # GitHub'dan verileri oku
        print("📖 GitHub'dan dosyalar okunuyor...")
        keys_data, keys_sha = get_github_file('verification_keys.json')
        users_data, users_sha = get_github_file('users.json')
        
        if not keys_data or not users_data:
            print("❌ GitHub dosyaları okunamadı!")
            return jsonify({
                "success": False,
                "message": "Sunucu hatası"
            }), 500
        
        print(f"✅ Dosyalar okundu")
        print(f"   Keys: {len(keys_data.get('keys', []))} adet")
        print(f"   Users: {len(users_data.get('users', []))} adet")
        
        # 1. YASAKLI HWID KONTROLÜ
        if hwid in keys_data.get('banned_hwids', []):
            print(f"🚫 Yasaklı HWID: {hwid}")
            
            return jsonify({
                "success": False,
                "message": "Bu cihaz yasaklanmıştır!"
            }), 403
        
        # 2. YASAKLI KULLANICI KONTROLÜ
        if username in users_data.get('banned_users', []):
            print(f"🚫 Yasaklı kullanıcı: {username}")
            
            return jsonify({
                "success": False,
                "message": "Bu kullanıcı yasaklanmıştır!"
            }), 403
        
        # 3. ANAHTAR KONTROLÜ (verification_keys.json)
        print(f"🔍 Anahtar aranıyor: {license_key}")
        key_found = None
        for key_obj in keys_data.get('keys', []):
            if key_obj['key'] == license_key:
                key_found = key_obj
                break
        
        if not key_found:
            print(f"❌ Anahtar bulunamadı: {license_key}")
            
            return jsonify({
                "success": False,
                "message": "Geçersiz ürün anahtarı!",
                "purchase_url": "https://www.itemsatis.com/p/PremiumSt0re"
            }), 401
        
        print(f"✅ Anahtar bulundu: {license_key}")
        
        # 4. ANAHTAR DURUM KONTROLÜ
        if key_found.get('status') != 'active':
            print(f"❌ Anahtar aktif değil: {key_found.get('status')}")
            return jsonify({
                "success": False,
                "message": "Bu ürün anahtarı aktif değil!"
            }), 403
        
        print(f"✅ Anahtar aktif")
        
        # 5. KULLANICI KONTROLÜ (users.json)
        print(f"🔍 Kullanıcı aranıyor: {username} / {license_key}")
        user_found = None
        for user in users_data.get('users', []):
            if user['license_key'] == license_key and user['owner'] == username:
                user_found = user
                break
        
        if not user_found:
            # İLK KULLANIM - YENİ KULLANICI OLUŞTUR
            print(f"🆕 Yeni kullanıcı oluşturuluyor...")
            
            new_user = {
                "license_key": license_key,
                "owner": username,
                "hwid": hwid,
                "registered_at": datetime.utcnow().isoformat(),
                "last_login": datetime.utcnow().isoformat()
            }
            
            users_data['users'].append(new_user)
            
            # Stats güncelle
            keys_data['stats']['active_keys'] = len([u for u in users_data['users']])
            
            # GitHub'a kaydet
            users_updated = update_github_file('users.json', users_data, users_sha, f"New user: {username}")
            keys_updated = update_github_file('verification_keys.json', keys_data, keys_sha, f"Stats update")
            
            if users_updated and keys_updated:
                print(f"✅ Yeni kullanıcı kaydedildi")
                
                return jsonify({
                    "success": True,
                    "message": "Giriş başarılı! Cihazınız kaydedildi.",
                    "first_use": True
                })
            else:
                print(f"❌ GitHub güncelleme başarısız")
                return jsonify({
                    "success": False,
                    "message": "Sunucu hatası"
                }), 500
        
        print(f"✅ Kullanıcı bulundu")
        
        # 6. HWID KONTROLÜ
        if user_found['hwid'] != hwid:
            print(f"🚫 HWID uyuşmuyor!")
            print(f"   Kayıtlı: {user_found['hwid']}")
            print(f"   Gelen: {hwid}")
            
            return jsonify({
                "success": False,
                "message": "Bu ürün anahtarı başka bir cihazda kullanılıyor!"
            }), 403
        
        print(f"✅ HWID eşleşti")
        
        # 7. BAŞARILI GİRİŞ - LAST LOGIN GÜNCELLE
        user_found['last_login'] = datetime.utcnow().isoformat()
        
        # GitHub'a kaydet
        users_updated = update_github_file('users.json', users_data, users_sha, f"Login: {username}")
        
        if users_updated:
            print(f"✅ Last login güncellendi")
            
            return jsonify({
                "success": True,
                "message": "Giriş başarılı!",
                "first_use": False
            })
        else:
            # Giriş başarılı ama GitHub güncellenemedi (önemli değil)
            print(f"⚠️ Last login güncellenemedi ama giriş başarılı")
            
            return jsonify({
                "success": True,
                "message": "Giriş başarılı!",
                "first_use": False
            })
    
    except Exception as e:
        print(f"❌ Doğrulama hatası: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": "Sunucu hatası"
        }), 500


@app.route('/verify_legacy', methods=['POST'])
def verify_legacy_user():
    """Eski kullanıcı doğrulama ve otomatik lisans oluşturma"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "message": "Geçersiz istek"}), 400
        
        auto_license_key = data.get('license_key')
        username = data.get('username')
        hwid = data.get('hwid')
        is_legacy = data.get('legacy', False)
        
        print(f"\n{'='*60}")
        print(f"🎖️ Eski Kullanıcı Kaydı:")
        print(f"   User: {username}")
        print(f"   Auto License: {auto_license_key}")
        print(f"   HWID: {hwid}")
        print(f"{'='*60}\n")
        
        if not auto_license_key or not username or not hwid or not is_legacy:
            return jsonify({
                "success": False,
                "message": "Eksik parametreler"
            }), 400
        
        # GitHub'dan verileri oku
        keys_data, keys_sha = get_github_file('verification_keys.json')
        users_data, users_sha = get_github_file('users.json')
        
        if not keys_data or not users_data:
            return jsonify({
                "success": False,
                "message": "Sunucu hatası"
            }), 500
        
        # 1. Yasaklı kontroller
        if hwid in keys_data.get('banned_hwids', []):
            return jsonify({
                "success": False,
                "message": "Bu cihaz yasaklanmıştır!"
            }), 403
        
        if username in users_data.get('banned_users', []):
            return jsonify({
                "success": False,
                "message": "Bu kullanıcı yasaklanmıştır!"
            }), 403
        
        # 2. Kullanıcı zaten kayıtlı mı?
        for user in users_data.get('users', []):
            if user['owner'] == username:
                # Zaten kayıtlı - HWID kontrolü
                if user['hwid'] == hwid:
                    return jsonify({
                        "success": True,
                        "message": "Zaten kayıtlısınız. Giriş başarılı!",
                        "first_use": False
                    })
                else:
                    return jsonify({
                        "success": False,
                        "message": "Bu kullanıcı başka bir cihazda kayıtlı!"
                    }), 403
        
        # 3. Yeni eski kullanıcı kaydı oluştur
        # verification_keys.json'a otomatik anahtar ekle
        new_key = {
            "key": auto_license_key,
            "status": "active"
        }
        keys_data['keys'].append(new_key)
        keys_data['stats']['total_keys'] = len(keys_data['keys'])
        keys_data['stats']['active_keys'] = len([k for k in keys_data['keys'] if k.get('status') == 'active'])
        
        # users.json'a kullanıcı ekle
        new_user = {
            "license_key": auto_license_key,
            "owner": username,
            "hwid": hwid,
            "registered_at": datetime.utcnow().isoformat(),
            "last_login": datetime.utcnow().isoformat(),
            "legacy": True  # Eski kullanıcı işareti
        }
        users_data['users'].append(new_user)
        
        # GitHub'a kaydet
        keys_updated = update_github_file('verification_keys.json', keys_data, keys_sha, f"Legacy user auto-key: {username}")
        users_updated = update_github_file('users.json', users_data, users_sha, f"Legacy user: {username}")
        
        if keys_updated and users_updated:
            print(f"✅ Eski kullanıcı kaydedildi: {username}")
            
            return jsonify({
                "success": True,
                "message": "Eski kullanıcı kaydı başarılı! Otomatik lisans oluşturuldu.",
                "first_use": True,
                "legacy": True
            })
        else:
            return jsonify({
                "success": False,
                "message": "Sunucu hatası"
            }), 500
    
    except Exception as e:
        print(f"❌ Eski kullanıcı doğrulama hatası: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": "Sunucu hatası"
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Railway için health check endpoint"""
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*60)
    print("🚀 PREMIUM STORE License API Starting...")
    print("="*60)
    print(f"🔡 Port: {port}")
    print(f"🔑 GitHub Token: {'✅ Set' if GITHUB_TOKEN else '❌ Not Set'}")
    print(f"📦 GitHub Repo: {GITHUB_REPO if GITHUB_REPO else '❌ Not Set'}")
    print(f"🌿 GitHub Branch: {GITHUB_BRANCH}")
    print(f"🚂 Platform: Railway")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=port)
