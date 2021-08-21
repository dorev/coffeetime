using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerMovement : MonoBehaviour
{
    private Rigidbody2D rigidBody;
    private Animator animator;
    private Vector2 movement;

    enum Orientation
    {
        Up,
        Right,
        Down,
        Left
    }

    private Orientation orientation = Orientation.Down;

    [Range(0f, 10f)]
    public float speed = 3f;

    void Start()
    {
        rigidBody = GetComponent<Rigidbody2D>();
        animator = GetComponent<Animator>();
    }

    void Update()
    {
        movement.x = Input.GetAxisRaw("Horizontal");
        movement.y = Input.GetAxisRaw("Vertical");
        animator.SetFloat("Horizontal", movement.x);
        animator.SetFloat("Vertical", movement.y);
        animator.SetFloat("Speed", movement.sqrMagnitude);

        if(movement.x > 0)
        {
            orientation = Orientation.Right;
        }
        else if(movement.x < 0)
        {
            orientation = Orientation.Left;
        }
        else if(movement.y > 0)
        {
            orientation = Orientation.Up;
        }
        else if(movement.y < 0)
        {
            orientation = Orientation.Down;
        }

        animator.SetInteger("Orientation", (int)orientation);
    }

    void FixedUpdate()
    {
        rigidBody.MovePosition(rigidBody.position + movement * speed * Time.fixedDeltaTime);
    }
}
