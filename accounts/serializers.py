from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import SavedAddress

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'phone', 'first_name', 'last_name')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'phone')

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', '')
        )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
        }
        return data


class SavedAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedAddress
        fields = (
            'id', 'label', 'first_name', 'last_name', 'address',
            'apartment', 'city', 'state', 'zip_code', 'country',
            'phone', 'landmark', 'is_default', 'created_at'
        )
        read_only_fields = ('id', 'created_at')

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if self.instance is None and user and user.is_authenticated:
            if SavedAddress.objects.filter(user=user).count() >= 3:
                raise serializers.ValidationError('You can save up to 3 addresses only.')
        return attrs